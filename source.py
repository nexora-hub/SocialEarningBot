#!/usr/bin/env python3

import re
import json
import socket
import asyncio
import requests
import traceback

from bs4 import BeautifulSoup
from module.online_storage import Download

from module.social_platforms.Twitter import X
from module.social_platforms.Telegram import TG
from module.social_platforms.Facebook import FB
from module.social_platforms.Instagram import IG

class SocialEarning:
      def __init__(self):
          """
          Initialize SocialEarningBot automation with headless mode and session configs
          """

          # ======= Browser / Execution State =======
          self.drive = None                   # Placeholder for driver instance (Playwright/automation driver)
          self.active = False                 # Indicates if automation is currently running
          self.se_context = None              #
          self.infinite_loop = False          # Controls main execution loop

          # ======= Data Tracking =======
          self.task_track = {}                # Track completed tasks
          self.start_time = None              # Record the start time of the automation
          self.posted_task = None             # Stores the maximum number of tasks detected from the site
          self.tasks_coroutine = {}           #
          self.blacklist_list = set()         # Stores blocked or skipped URLs/users
          self.running_platforms = set()      # Active platforms currently running under automation

          # ======= Networking / Persistence =======
          self.persist_session = requests.Session() # Persistent HTTP session for requests

          # ======= Concurrency Control =======
          self.semaphore = asyncio.Semaphore(1)  # Limit concurrency async workers (prevents resource exhaustion)
          self.task_process_semaphore = asyncio.Semaphore(5) # Controls how many tasks can be submitted in parallel

          # ======= Credentials / Session Storage =======
          self.credentials_path = 'credentials.json'        # Default credentials file path
          self.storage_state_file = 'storage_state.json'    # Default storage state file
          self.telegram_session_file = 'Telegram.session'   # Telegram session file path

          # Initialize/synchronize supported platforms
          self.sync_platforms()

      def is_port_in_use(self, port):
          with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
               return s.connect_ex(("127.0.0.1", port)) == 0

      def error_traceback(self, error):
          # Get traceback details from the exception
          error_info = traceback.extract_tb(error.__traceback__)

          # Return empty fields if no traceback found
          if not error_info:
             return {"func": None, "code": None, "lineno": None, "filename": None}

          # Extract last call (actual error point)
          filename, lineno, func, code = error_info[-1]

          # Return structured error details
          return {
             "code": code,          # Line of code that triggered the error
             "error": str(error),   # Error message as string
             "lineno": lineno,      # Line number of the error
             "function": func,      # Name of the function where error occurred
             "filename": filename   # Path of the file containing the error
          }

      def sync_platforms(self):
          # ======= Endpoint for Media Task =======
          self.twitter_task_endpoint = 'https://socialearning.org/earner/available/tasks?filter_social_media=3'
          self.facebook_task_endpoint = 'https://socialearning.org/earner/available/tasks?filter_social_media=5'
          self.telegram_task_endpoint = 'https://socialearning.org/earner/available/tasks?filter_social_media=11'
          self.instagram_task_endpoint = 'https://socialearning.org/earner/available/tasks?filter_social_media=2'

          # ======= Platform Disable Flags =======
          self.twitter_disable = False
          self.facebook_disable = True
          self.telegram_disable = False
          self.instagram_disable = False

          # ======= Platform Concurrency Locks =======
          self.twitter_lock = asyncio.Lock()
          self.facebook_lock = asyncio.Lock()
          self.telegram_lock = asyncio.Lock()
          self.instagram_lock = asyncio.Lock()

          # ======= Synchronization Flags =======
          self.sync_data = None           # Overall session/account sync state
          self.sync_twitter = False       # Twitter account sync state
          self.sync_facebook = False      # Facebook account sync state
          self.sync_telegram = False      # Telegram account sync state
          self.sync_instagram = False     # Instagram account sync state

          # ======= Platform Worker Registry =======
          self.platform_worker = {
              "Twitter": self.twitter,
              "Facebook": self.facebook,
              "Telegram": self.telegram,
              "Instagram": self.instagram
          }

          # ======= Media Tasks Type =======
          self.telegram_task_types = [
              'TELEGRAM/Group',
              'TELEGRAM/Channel'
          ]

          self.twitter_task_types = [
              'X/Tweet Like',
              'X/Tweet Views',
              'X/Page Follow',
              'X/Tweet Repost',
              'X/Tweet Comment'
          ]

          self.instagram_task_types = [
              'INSTAGRAM/Post Like',
              'INSTAGRAM/Page Follow',
              'INSTAGRAM/Post Comment'
          ]

          self.facebook_task_types = [
              'FACEBOOK/Page Like',
              'FACEBOOK/Page Follow'
          ]

      def sync_credentials(self):
          # List of required files for a valid session
          files = [
             self.credentials_path,
             self.storage_state_file,
             self.telegram_session_file,
          ]

          # Loop through each file and verify it exists or downloads successfully
          for file in files:
              # Abort if any of the files fail to download or are missing
              if not Download(file):
                 return print ("\033[96mSocialEarningBot → sync_credentials\033[0m(\033[91merror\033[0m): session data initialization failed")

          # Open the credentials JSON file
          with open('storage/' + self.credentials_path, "r") as file:
               # Load the JSON content into self.data for later use
               self.data = json.load(file)

          # Indicate that credentials were successfully synced
          return True

      async def track_platform(self, platform: str, add: bool=False):
            try:
              if add:
                 # Add platform (no duplicates)
                 self.running_platforms.add(platform)

              else:
                 # Remove platform safely if exists
                 self.running_platforms.discard(platform)

            except Exception as error:
                   await self.drive.helper.print(f'[\033[93mSDE\033[0m]|\033[96mSocialEarning → track_platform\033[0m(\033[91merror\033[0m): {error}')

      async def platform_workers(self):
            try:
              # Loop through each platform and its corresponding worker function
              for platform, workers in self.platform_worker.items():
                  # Only start the worker if:
                  #   1. The platform is not already marked as running
                  if platform not in self.running_platforms:
                     # Schedule the worker as a background asyncio task
                     # (fire-and-forget, does not block current execution)
                     asyncio.create_task(workers())

            except Exception as error:
                   # Log any unexpected errors encountered during execution
                   await self.drive.helper.print(f"[\033[93mSDE\033[0m]|\033[96mSocialEarningBot → platform_workers\033[0m(\033[91merror\033[0m): {self.error_traceback(error)}")

      async def mount_persist_session(self, page):
            # Asynchronously inject each cookie into the persistent session
            for cookie in await page.context.cookies():
                # Inject a cookie into the persistent session
                self.persist_session.cookies.set(
                    cookie['name'], cookie['value'],           # Set the cookie's name and value
                    path=cookie.get('path'),                   # Set the path for the cookie (optional)
                    secure=cookie.get('secure'),               # Mark cookie as secure (optional)
                    domain=cookie.get('domain')                # Set the domain for the cookie (optional)
                )

      async def initialize(self, page: bool=None):
            # Predefined error messages for common failure scenarios
            message = {
               "error": '[\033[93mSDE\033[0m]|\033[96mSocialEarning → initialize\033[0m(\033[91merror\033[0m): Oops! Something went wrong',
               "active": "[\033[93mSDE\033[0m]|\033[96m\033[4mSocialEarningBot → initialize\033[0m(\033[95msession\033[0m): Session initialized successfully",
               "session": '[\033[93mSDE\033[0m]|\033[96mSocialEarning → initialize\033[0m(\033[91mfailed\033[0m): Online Session expired',
               "internet": '[\033[93mSDE\033[0m]|\033[96mSocialEarning → initialize\033[0m(\033[91merror\033[0m): Poor Internet'
            }

            try:
              # Open a new browser page (tab) within the retrieved context
              page = await self.drive.new_window(self.se_context)

              # Try to navigate to the SocialEarning sign-in page
              if not await self.drive.helper.site_lamba('https://socialearning.org/sign-in', page, timeout=30, silent=True):
                 # Print an internet connectivity error message if navigation fails
                 await self.drive.helper.print(message['internet'])

              # If redirected to dashboard, session is still valid
              if not page.url.startswith('https://socialearning.org/earner/dashboard'):
                 # If on sign-in page → session expired
                 if page.url.startswith('https://socialearning.org/sign-in'):
                    await self.drive.helper.print(message['session'])
                 else:
                    # Unexpected state (not dashboard, not sign-in) → prompt user
                    await self.drive.helper.print(message['error'])

                 # Return False to indicate that the session is not valid
                 return False

              # Mark credentials as successfully synced
              self.sync_data = True

              # Mount a persistent session for reuse
              await self.mount_persist_session(page)

              # Display a message indicating the session is now active
              await self.drive.helper.print(message["active"])

              # Return True indicating that the session is valid
              return True

            except Exception as error:
                # Log any unexpected errors encountered during execution
                await self.drive.helper.print(f"[\033[93mSDE\033[0m]|]\033[96mSocialEarningBot → initialize\033[0m(\033[91merror\033[0m): {self.error_traceback(error)}")

            finally:
                # Ensure page is closed to free browser resources
                if page and not page.is_closed():
                   await page.close()

      async def start(self, context: bool=None):
            """
            Entry point for executing the automation workflow
            Handles credentials syncing, initializes browser session, and begins task execution
            """

            try:
              # If sync_data is still False → session has not been initialized yet
              if not self.sync_data:
                 # sync credentials
                 if not self.sync_credentials():
                    # Abort if credentials could not be loaded
                    return False

                 # Create a new Playwright browser context
                 if not self.se_context:
                    self.se_context = await self.drive.playwright_context()

                 # Mark SocialEarning as currently running
                 await self.track_platform('SocialEarning', add=True)

                 # Run initialization (login/session setup, cookies, state, etc.)
                 if not await self.initialize():
                    # Reset sync flag if initialization failed
                    self.sync_data = False

                    # Stop execution if initialization failed
                    return False

              # At this point, credentials are synced and session is initialized
              # → Start platform-specific workers (Twitter, Telegram, etc.)
              await self.platform_workers()

            except Exception as error:
               # Log any unexpected errors encountered during execution
               print (f"\n[\033[93mSDE\033[0m]|\033[96mSocialEarningBot → start\033[0m(\033[91merror\033[0m): {self.error_traceback(error)}")

            finally:
               # Ensure SocialEarning is untracked from running platforms even if an error occurs
               await self.track_platform('SocialEarning')

      async def telegram(self, context: bool=None):
            try:
              # Verify that Telegram is enabled and tasks are available before proceeding
              if self.telegram_disable or not await self.task_availability(self.telegram_task_types, self.telegram_task_endpoint):
                 return False

              # Use a dedicated lock to prevent multiple Telegram workers
              async with self.telegram_lock:
                    # If Telegram is already marked as running, skip starting another
                    if 'Telegram' in self.running_platforms:
                       return False

                    # Mark Telegram as an active running platform
                    await self.track_platform('Telegram', add=True)

              # Limit concurrent heavy operations using a shared semaphore
              async with self.semaphore:
                    # Create a Playwright browser context for this Telegram session
                    context = await self.drive.playwright_context()

                    if self.infinite_loop:
                       # Run Telegram automation tasks using TG handler
                       await TG(self).start(context)

            except Exception as error:
                   # Catch and log any errors during Telegram task execution
                   await self.drive.helper.print(f'[\033[93mSDE\033[0m]|\033[96mSocialEarning → telegram\033[0m(\033[91merror\033[0m): {self.error_traceback(error)}')

            finally:
               # Ensure Telegram is removed from running platforms even if an error occurs
               await self.track_platform('Telegram')

               # If a Playwright browser context was created
               if context:
                  # Close it to free memory/resources
                  await context.close()

      async def instagram(self, context: bool=None):
            try:
              # Verify that Instagram is enabled and tasks are available before proceeding
              if self.instagram_disable or not await self.task_availability(self.instagram_task_types, self.instagram_task_endpoint):
                 return False

              # Use a dedicated lock to prevent multiple Instagram workers
              async with self.instagram_lock:
                    # If Instagram is already marked as running, skip starting another
                    if 'Instagram' in self.running_platforms:
                       return False

                    # Mark Instagram as an active running platform
                    await self.track_platform('Instagram', add=True)

              # Limit concurrent heavy operations using a shared semaphore
              async with self.semaphore:
                    # Create a Playwright browser context for this Instagram session
                    context = await self.drive.playwright_context()

                    if self.infinite_loop:
                       # Run Instagram automation tasks using IG handler
                       await IG(self).start(context)

            except Exception as error:
                   # Catch and log any errors during Instagram task execution
                   await self.drive.helper.print(f'[\033[93mSDE\033[0m]|\033[96mSocialEarning → instagram\033[0m(\033[91merror\033[0m): {self.error_traceback(error)}')

            finally:
               # Ensure Instagram is untracked from running platforms even if an error occurs
               await self.track_platform('Instagram')

               # If a Playwright browser context was created
               if context:
                  # Close it to free memory/resources
                  await context.close()

      async def facebook(self, context: bool=None):
            try:
              # Verify that Facebook is enabled and tasks are available before proceeding
              if self.facebook_disable or not await self.task_availability(self.facebook_task_types, self.facebook_task_endpoint):
                 return False

              # Use a dedicated lock to prevent multiple Facebook workers
              async with self.facebook_lock:
                    # If Facebook is already marked as running, skip starting another
                    if 'Facebook' in self.running_platforms:
                       return False

                    # Mark Facebook as an active running platform
                    await self.track_platform('Facebook', add=True)

              # Limit concurrent heavy operations using a shared semaphore
              async with self.semaphore:
                    # Create a Playwright browser context for this Facebook session
                    context = await self.drive.playwright_context()

                    if self.infinite_loop:
                       # Run Facebook automation tasks using FB handler
                       await FB(self).start(context)

            except Exception as error:
                   # Catch and log any errors during Facebook task execution
                   await self.drive.helper.print(f'[\033[93mSDE\033[0m]|\033[96mSocialEarning → facebook\033[0m(\033[91merror\033[0m): {self.error_traceback(error)}')

            finally:
               # Ensure Facebook is untracked from running platforms even if an error occurs
               await self.track_platform('Facebook')

               # If a Playwright browser context was created
               if context:
                  # Close it to free memory/resources
                  await context.close()

      async def twitter(self, context: bool=None):
            try:
              # Verify that Twitter is enabled and tasks are available before proceeding
              if self.twitter_disable or not await self.task_availability(self.twitter_task_types, self.twitter_task_endpoint):
                 return False

              # Use a dedicated lock to prevent multiple Twitter workers
              async with self.twitter_lock:
                    # If Twitter is already marked as running, skip starting another
                    if 'Twitter' in self.running_platforms:
                       return False

                    # Mark Twitter as an active running platform
                    await self.track_platform('Twitter', add=True)

              # Limit concurrent heavy operations using a shared semaphore
              async with self.semaphore:
                    # Create a Playwright browser context for this Twitter session
                    context = await self.drive.playwright_context()

                    if self.infinite_loop:
                       # Run Twitter automation tasks using IG handler
                       await X(self).start(context)

            except Exception as error:
                   # Catch and log any errors during Twitter task execution
                   await self.drive.helper.print(f'[\033[93mSDE\033[0m]|\033[96mSocialEarning → twitter\033[0m(\033[91merror\033[0m): {self.error_traceback(error)}')

            finally:
               # Ensure Twitter is untracked from running platforms even if an error occurs
               await self.track_platform('Twitter')

               # If a Playwright browser context was created
               if context:
                  # Close it to free memory/resources
                  await context.close()

      async def task_availability(self, task_types, task_endpoint):
            try:
              # Perform two HEAD requests concurrently for higher reliability
              response = self.persist_session.get(task_endpoint, timeout=10)

              # If the response did not return HTTP 200 OK
              if not response.status_code == 200:
                 # Print the error details including response code and URL
                 await self.drive.helper.print(f'[\033[93mSDE\033[0m]|\033[96mTask-Availability\033[0m(\033[91m{response.status_code}\033[0m): {response.text[:50]}')

              # Check if the current page URL is the sign-in page
              if response.url.startswith('https://socialearning.org/sign-in'):
                 # Stop task execution loop due to expired session or logout
                 self.sync_data, self.infinite_loop = False, False

                 # Signal that the session has ended
                 return await self.drive.helper.print( # Print error message: user session expired or logged out
                    '\n[\033[93mSDE\033[0m]|\033[96mSocialEarning\033[0m(\033[93minfo\033[0m): Detected redirection to login page — session may have expired or user was logged out'
                 )

              # Loop through extracted task links
              for tasks_url in await self.drive.helper.extract_links(response.text, 'next=/earner/available/'):
                  # Get numeric ID from task link
                  task_id =  re.findall(r'\d+', tasks_url)[0]

                  # Skip if already processed
                  if task_id in self.task_track:
                     continue

                  # Skip if the task is banned
                  if not await self.blacklist(f'https://socialearning.org{tasks_url}'):
                     # Check if task type exists in response
                     for task in task_types:
                         if task in response.text:
                            return True  # Task comfirmed

              # No executable tasks found
              return False

            except Exception as error:
                   await self.drive.helper.print(f'[\033[93mSDE\033[0m]|\033[96mSocialEarning → task_availability\033[0m(\033[91merror\033[0m): {error}')

      async def posted_taskes(self):
            try:
              # Send a GET request to the 'done tasks' endpoint
              response = self.persist_session.get('https://www.socialearning.org/earner/done/tasks', timeout=10)
            except Exception as error:
                   # If request fails, log the error and return False
                   return await self.drive.helper.print(f'[\033[93mSDE\033[0m]|\033[96mSocialEarning → posted_task\033[0m(\033[91merror\033[0m): {str(error)}')

            # If the response did not return HTTP 200 OK
            if not response.status_code == 200:
               # Print the error details including response code and URL
               await self.drive.helper.print(f'[\033[93mSDE\033[0m]|\033[96mPosted Task\033[0m(\033[91m{response.status_code}\033[0m): {response.text[:50]}')

            # Detect if redirected to the login page (session expired)
            if response.url.startswith('https://socialearning.org/sign-in'):
               # Stop task execution loop due to expired session or logout
               self.sync_data, self.infinite_loop = False, False

               # Signal that the session has ended
               return await self.drive.helper.print( # Print error message: user session expired or logged out
                  '\n[\033[93mSDE\033[0m]|\033[96mSocialEarning\033[0m(\033[93minfo\033[0m): Detected redirection to login page — session may have expired or user was logged out'
               )

            # Parse HTML for task information
            parser = BeautifulSoup(response.text, "html.parser")
            target_span = parser.select_one("div.marquee span")

            # Handle missing element case
            if not target_span:
               # Exit early if no span element exists
               return False, await self.drive.helper.print('[\033[93mSDE\033[0m]|\033[96mSocialEarning → posted_task\033[0m: No marquee span element found')

            # Extract the maximum task number from the text
            max_task_match = re.findall(r'\d+', target_span.get_text(strip=True))

            # If a valid number is found, store it as posted_task
            if max_task_match:
               self.posted_task = max_task_match[0]

      async def check_task_availability(self):
            # Define supported task workers with their types and endpoints
            task_workers = {
                "Twitter": {
                   "types": self.twitter_task_types,
                   "disable": self.twitter_disable,
                   "endpoint": self.twitter_task_endpoint
                },
                "Telegram": {
                   "types": self.telegram_task_types,
                   "disable": self.telegram_disable,
                   "endpoint": self.telegram_task_endpoint

                },
                "Facebook": {
                   "types": self.facebook_task_types,
                   "disable": self.facebook_disable,
                   "endpoint": self.facebook_task_endpoint

                },
                "Instagram": {
                   "types": self.instagram_task_types,
                   "disable": self.instagram_disable,
                   "endpoint": self.instagram_task_endpoint
                }
            }

            # Define async processes list
            async_proceses = []

            # Queue availability checks for each platform
            for platform, config in task_workers.items():
                # Skip if platform is disabled or platform is not already running
                if config["disable"] or platform in self.running_platforms:
                   continue

                async_proceses.append(self.task_availability(config["types"], config["endpoint"]))

            # Include posted_task check in async processes
            async_proceses.append(self.posted_taskes())

            # Run all availability checks concurrently and return True if any are available
            if any(await asyncio.gather(*async_proceses)):
               return True

            # No tasks available for any platform
            return False

      async def blacklist(self, value, banned: bool = False):
            """
            Manage a blacklist of banned tasks

            Args:
            - value (iterable): List or single value to check or add to the blacklist
            - banned (bool, optional): If True, add values to the blacklist. Defaults to False

            Returns:
            - bool: True if the value is already in the blacklist, otherwise None
            """

            try:
              # Ensure values are iterable (listify even if a single string is passed)
              for string in await self.drive.helper.mklist(value):
                  if banned:
                     # Add string to blacklist set
                     self.blacklist_list.add(string)

                  else:
                     # If value is already blacklisted, return True
                     if string in self.blacklist_list:
                        return True

            except Exception as error:
                   # Catch and log any unexpected error during blacklist management
                   await self.drive.helper.print(f"\n\033[96mSocialEarningBot → blacklist\033[0m(\033[91merror\033[0m): {str(error)}")
