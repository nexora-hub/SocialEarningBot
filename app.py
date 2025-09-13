#!/usr/bin/env python3

import os
import json
import time
import psutil
import asyncio
import threading
import subprocess

from source import SocialEarning
from module.nexora import async_api
from playwright.async_api import async_playwright
from flask import Flask, url_for, Response, redirect, request, jsonify, send_file, render_template



# Initialize Flask app
app = Flask(__name__)

@app.route("/")
def index():
    # ───────────────────────────────────────────────
    # Render the 'index.html' template when the root URL is accessed
    # ───────────────────────────────────────────────
    return render_template("index.html")

@app.route('/favicon.ico')
def favicon():
    # ───────────────────────────────────────────────
    # Return your custom image as the favicon
    # ───────────────────────────────────────────────
    return send_file("static/favicon.png", mimetype="image/png")

@app.route("/view/tasks", methods=["GET"])
def view_tasks():
    # ───────────────────────────────────────────────
    # Render and return the HTML page that displays the list of tasks
    # ───────────────────────────────────────────────
    return render_template("view_tasks/index.html")

@app.route("/api/chart-metrics")
def ChartMetrics():
    # ───────────────────────────────────────────────
    # Stream live metrics continuously (Every 3sec. SSE endpoint)
    # ───────────────────────────────────────────────
    return Response(metrics_stream(TIME=3), mimetype="text/event-stream")

@app.route("/api/active-platform")
def ActivePlatform():
    # ───────────────────────────────────────────────
    # Stream live metrics continuously (Every 1sec. SSE endpoint)
    # ───────────────────────────────────────────────
    return Response(metrics_stream(TIME=1), mimetype="text/event-stream")

@app.route("/api/context-metrics")
def ContextMetrics():
    # ───────────────────────────────────────────────
    # Stream live metrics continuously (Every 1sec. SSE endpoint)
    # ───────────────────────────────────────────────
    return Response(metrics_stream(TIME=1), mimetype="text/event-stream")

@app.route("/api/task/reset", methods=["GET"])
def reset_task_queue():
    # ───────────────────────────────────────────────
    # Clears all tracked task entries from the bot's task queue
    # Useful for resetting the state before a new run
    # ───────────────────────────────────────────────

    # Reset the task status dictionary to empty
    bot.task_track = {}

    # Confirm that the task queue was successfully cleared
    return jsonify({"message": "Task queue successfully cleared"})


@app.route("/api/task/list", methods=["GET"])
def task_logs():
    # ───────────────────────────────────────────────
    # Endpoint: Return all tracked task logs from bot
    # Provides JSON response of current task states
    # ───────────────────────────────────────────────
    try:
      # Return the current status of all tracked tasks
      return jsonify({"message": bot.task_track})

    except Exception as error:
           # Return error details with 500 Internal Server Error
           return jsonify({"error": str(error)}), 500


@app.route("/shutdown")
def exit():
    # ───────────────────────────────────────────────
    # Handle shutdown request for the Flask server
    # ───────────────────────────────────────────────

    try:
      # If bot is already inactive → return notice
      if not bot.active:
         return jsonify({"message": "Flask server is down!"})

      # Stop main execution loop (halts automation tasks)
      bot.infinite_loop = False

    except Exception as error:
           # Handle unexpected errors during shutdown
           return jsonify({"error": str(error)}), 500

    # Confirm shutdown signal was sent successfully
    return jsonify({"message": "sending shut down signal"})

@app.route('/xpra/exit', methods=["GET"])
def stop_Xpra_session():
    # ───────────────────────────────────────────────
    # Endpoint: Stop active Xpra session
    # Executes "xpra stop" and redirects to home page
    # ───────────────────────────────────────────────
    try:
        # Run "xpra stop" and capture output
        result = subprocess.run(
            ["xpra", "stop"],
            text=True,
            check=True,
            capture_output=True
        )

    except subprocess.CalledProcessError as error:
        # "xpra stop" failed with non-zero exit code
        return jsonify({
            "error": error.stderr.strip(),
            "message": "Failed to stop Xpra"
        }), 500

    except Exception as error:
        # Catch unexpected errors with traceback
        return jsonify({
            "error": str(error),
            "trace": bot.error_traceback(error)
        }), 500

    # Redirect back to home if successful
    return redirect("/")

@app.route("/start", methods=["GET"])
def request_handler():
    # ───────────────────────────────────────────────
    # Safely handle bot start requests
    # ───────────────────────────────────────────────
    with request_lock:
         # If already running → skip duplicate start
         if bot.active:
            return jsonify({"message": "SocialEarningBot already initiated"})

         # Mark bot as active before launching thread
         bot.active = True

    try:
      # Launch automation logic in daemon thread (non-blocking)
      threading.Thread(target=execute_automation, daemon=True).start()

    except Exception as error:
      # Catch startup errors and return JSON response
      return jsonify({
          "error": str(error),
          "message": "Oops! something went wrong"
      }), 500

    # Confirm start request accepted
    return jsonify({"message": "starting socialearningbot..."})

@app.route("/remote/desktop", methods=["GET"])
def virtual_session(PORT: int=10000, HOST: str="socialearningbot.fly.dev"):
    # ───────────────────────────────────────────────
    # Endpoint: Launch a remote desktop (Xpra session)
    # ───────────────────────────────────────────────

    # Prevent duplicate Xpra instances on the same port
    if bot.is_port_in_use(PORT):
       return jsonify({"message": "Xpra already running"}), 409

    # ───────────────────────────────────────────────
    # Launch Xpra as a detached background process
    # ───────────────────────────────────────────────
    try:
      subprocess.Popen([
          "xpra", "start", ":100",       # :100 → Virtual display number (isolated X11 session)

          # ───── Xpra Web Client Settings ─────
          "--html=on",                   # Enable built-in HTML5 client (accessible via browser)
          "--mdns=no",                   # Disable mDNS service discovery (prevents LAN broadcast)
          "--exit-with-children",        # Kill Xpra automatically when child process exits
          "--bind-tcp=0.0.0.0:10000",    # Bind TCP listener on all interfaces, port 10000

          # ───── Performance & Encoding Tweaks ─────
          "--speed=30",                  # Speed vs quality tradeoff (lower = more compression)
          "--webcam=no",                 # Disable webcam redirection for security
          "--compress=0",                # Disable additional compression (CPU saving)
          "--quality=90",                # Default quality setting (higher = better clarity)
          "--min-speed=20",              # Minimum speed threshold (helps avoid stuttering)
          "--encoding=h265",             # Use H.265 video codec (efficient compression)
          "--min-quality=90",            # Minimum image quality
          "--notifications=no",          # Suppress X11 desktop notifications in session
          "--auto-refresh-delay=0.2",    # Refresh delay for screen changes (seconds)
          "--video-encoders=x265,x264",  # List of allowed video encoders

          # ───── Start Application Inside Xpra ─────
          "--start-child=python3 module/session_handler.py"  # Child process launched inside virtual display
      ])

    except Exception as error:
           # Return JSON response containing message, and failed status
           return jsonify({
               "error": str(error),
               "message": "Oops! something went wrong"
           }), 500

    # ───────────────────────────────────────────────
    # Build Xpra HTML5 client URL with safe defaults
    # ───────────────────────────────────────────────
    XPRA_ARGS = f"connect.html?server={HOST}&port=&printing=false&file_transfer=false&floating_menu=false&bandwidth_limit=1000000"

    # Give Xpra a few seconds to initialize
    time.sleep(10)

    # Redirect user’s browser to the Xpra HTML5 client path
    return redirect(f"https://{HOST}/xpra/session/{XPRA_ARGS}", code=302)


def percent_to_cpu(max_cpu, percent):
    # ───────────────────────────────────────────────
    # Convert CPU percentage into core-equivalent value
    # ───────────────────────────────────────────────

    # Scale usage to cores
    cpu_value = max_cpu * (percent / 100.0)

    # Round result to 2 decimals
    return round(cpu_value, 2)


def reset_values():
    # Clear runtime collection blacklist to start fresh
    bot.blacklist_list.clear()

    # Reset core state flags/attributes to defaults
    # - drive / posted_task / start_time → None (no active context)
    # - active / sync_data / infinite_loop → False (idle + safe state)

    bot.active, bot.sync_data, bot.infinite_loop = False, False, False
    bot.drive, bot.start_time, bot.se_context, bot.posted_task = None, None, None, None


def metrics_stream(TIME: int=1):
    # ───────────────────────────────────────────────
    # Generator: continuously stream live system metrics
    # Format: Server-Sent Events (SSE)
    # ───────────────────────────────────────────────
    while True:
          # Fetch latest metrics snapshot
          metrics = live_metrics()

          # Yield SSE-compatible payload
          yield f"data: {json.dumps(metrics)}\n\n"

          # Throttle updates
          time.sleep(TIME)


def execute_automation():
    """
    Function that executes the browser automation using Playwright inside an async context.
    Runs in a separate thread to prevent blocking the main Flask app.
    """

    try:
      # Record the start time of the automation
      bot.start_time = time.time()

      # Flag to enable continuous execution
      bot.infinite_loop = True

      # Clear the storage/image directory to clean up residual files
      purge_directory()

      # Launch the main async automation entry point
      asyncio.run(launch_socialearning())

    except Exception as error:
      # Log any error that occurs during execution
      print (f'\033[96mSocialEarningBot\033[0m(\033[91merror\033[0m): {bot.error_traceback(error)}')

    finally:
      reset_values()

    # Log shutdown message after task loop ends
    print ('\033[96mSocialEarningBot\033[0m(\033[95mmessage\033[0m): \033[91mshutting down!\033[0m')


async def automation_loop(task_search: bool = None):
      # Infinite loop to continuously perform tasks
      while bot.infinite_loop:
            # If task_search flag is not explicitly set to False, start the bot
            if task_search is not False:
               if await bot.start() is False:
                  break  # Break loop if bot.start() fails

            # If bot session is synced/initialized, check if new tasks are available
            if bot.sync_data is True:
               task_search = await bot.check_task_availability()

            # If no tasks are available, notify via console
            if task_search is False:
               print ("\033[96mTasks\033[0m(\033[95mcurrent\033[0m): unavailable!")

            # Perform a short wait loop (10 seconds total, 1-second intervals)
            for _ in range(10):
                # Break early if infinite loop flag is disabled externally
                if not bot.infinite_loop:
                   break

                # Sleep to prevent busy-waiting / high CPU usage
                await asyncio.sleep(1)


def purge_directory():
    # ───────────────────────────────────────────────
    # Target directories to purge
    # ───────────────────────────────────────────────
    for dir_path in ['storage/image/', 'storage/run_time/']:
        try:
          # Skip if directory doesn't exist
          if not os.path.exists(dir_path):
             continue

          # Iterate efficiently over directory contents
          for entry in os.scandir(dir_path):
              try:
                # Only delete regular files (ignore folders/symlinks)
                if entry.is_file():
                   os.remove(entry.path)

              except Exception as error:
                     # Log any errors during deletion (permissions, file in use, etc.)
                     print (f"\033[93m[info]\033[0m|\033[96mpurge_directory\033[0m(\033[91merror\033[0m): {str(error)}")

        except Exception as error:
               # Log directory-level errors (e.g., no access to dir)
               print (f"\033[93m[info]\033[0m|\033[96mpurge_directory\033[0m(\033[91merror\033[0m): {str(error)}")


async def launch_socialearning():
      """
      Main automation entry point
      Starts Playwright, initializes browser automation, launches workers
      """

      # Start Playwright, initialize the browser, and execute the main logic
      async with async_playwright() as plugin:
            try:
              # Initialize automation driver with browser context and saved session state
              bot.drive = await async_api(plugin, headless=False).initalize(bot)

              # Run task loop
              await automation_loop()

              # Wait until all running platform workers finish before closing
              while bot.running_platforms:
                    # Sleep to prevent high CPU usage
                    await asyncio.sleep(5)

              # Collect and finalize any scheduled coroutines
              if bot.tasks_coroutine:
                 await asyncio.gather(
                      *list(bot.tasks_coroutine.values()),
                       return_exceptions = True
                 )

            except Exception as error:
               # Log any error that occurs during execution
               print (f'\033[96mSocialEarningBot\033[0m(\033[91merror\033[0m): {bot.error_traceback(error)}')

            finally:
               # Ensure browser is closed to free resources
               if bot.drive:
                  await bot.drive.close_browser()


def live_metrics():
    # ───────────────────────────────────────────────
    # Collect snapshot of system + bot runtime metrics
    # Combines CPU, RAM, task progress, and uptime info
    # ───────────────────────────────────────────────

    # ======== CPU metrics ========
    cpu_core = psutil.cpu_count()                     # Total number of CPU cores
    cpu_percent = psutil.cpu_percent(interval=None)   # Current CPU usage percentage
    cpu_usage = percent_to_cpu(cpu_core, cpu_percent) # Convert % usage into core-equivalent value

    # ======== Memory metrics ========
    virtual_memory = psutil.virtual_memory()
    ram_percent = virtual_memory.percent              # RAM usage percentage
    ram_core = virtual_memory.total // (1024*1024)    # Total RAM in MB
    ram_usage = virtual_memory.used // (1024*1024)    # Used RAM in MB

    # ======== Bot runtime metrics ========
    uptime_seconds = int(time.time() - bot.start_time) if bot.active else 0

    # ───────────────────────────────────────────────
    # Structured JSON payload
    # ───────────────────────────────────────────────
    return {
       "ram_percent": ram_percent,                                      # RAM usage percentage
       "cpu_percent": cpu_percent,                                      # CPU usage percentage
       "posted_task": bot.posted_task,                                  # Highest recorded task count
       "tasks_completed": len(bot.task_track),                          # Total tasks completed
       "active_platform": list(bot.running_platforms),                  # Platforms currently running
       "status": "active" if bot.active else "inactive",                # Bot status string
       "cpu_usage": f"{cpu_usage} | {cpu_percent}% | {cpu_core} CPU",   # CPU usage summary
       "ram_usage": f"{ram_usage} | {ram_percent}% | {ram_core} RAM",   # RAM usage summary
       "uptime": time.strftime("%H:%M:%S", time.gmtime(uptime_seconds)) # Bot uptime (HH:MM:SS)
    }

# Initialize SocialEarning instance
bot = SocialEarning()

bot.start_time = time.time()

# Threading lock for concurrency control
request_lock = threading.Lock()

if __name__ == "__main__":
   # Start the Flask server using Render's assigned port or default to 5000
   app.run(host="0.0.0.0", port = int(os.getenv("PORT", 5000)))
