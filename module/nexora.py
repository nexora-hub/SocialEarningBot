#!/usr/bin/env python3

import os
import re
import math
import socket
import random
import asyncio
import aiofiles
import requests


from bs4 import BeautifulSoup
from datetime import datetime
from .online_storage import Upload


class async_api:
      def __init__(self, plugin, headless: bool=False):
          """
          Initializes the class instance with required parameters.

          Args:
          - plugin (str): The plugin name or path.
          - headless (bool, optional): Whether to run in headless mode. Defaults to False.
          """

          self.plugin = plugin       # Plugin instance
          self.headless = headless   # Flag to run browser in headless mode

      async def initalize(self, source):
            """
            Initialize the Playwright browser driver with specific configurations

            Responsibilities:
            - Launches a Chromium browser instance (Chrome channel)
            - Applies startup arguments to reduce automation fingerprints
            - Respects the "headless" flag to toggle GUI visibility
            - Instantiates the helper class for utility functions tied to this driver
            """

            # Browser launch arguments:
            # - --start-maximized: ensures browser starts in maximized mode (important for sites that hide UI on small screens)
            # - --disable-infobars: removes "Chrome is being controlled by automated test software" notification
            # - --disable-blink-features=AutomationControlled: hides common Playwright/automation detection signals
            BROWSER_ARGS = [
                "--no-sandbox",
                "--disable-infobars",
                "--disable-blink-features=AutomationControlled"
            ]

            # Launch the Chromium browser (via Chrome channel for better site compatibility)
            self.browser = await self.plugin.chromium.launch(
                channel="chrome",
                args=BROWSER_ARGS,
                headless=self.headless  # If True: fully invisible. If False: opens visible Chrome window for debugging.
            )

            # Initialize the automation helper (wrapping Playwright primitives with
            # reusable high-level actions: clicking, waiting selectors, etc.)
            self.helper = function(self, source)

            # Return the instance itself, enabling chained calls
            return self

      async def playwright_context(self):
            """
            Create a new browser context (isolated session).

            Key points:
            - Each context is like a separate incognito window:
              cookies, local storage, and sessions are unique per context.
            - Allows multiple accounts or sessions to run in the same browser without interference.
            - Storage state file enables session persistence (avoids logging in every run).
            """

            return await self.browser.new_context(
                locale="en-US",
                viewport = {"width": 1480, "height": 820},   # Set the browser viewport size
                color_scheme="dark",                         # Forces dark mode; can affect site layouts and testing consistency
                storage_state="storage/storage_state.json",  # Load cookies & localStorage if file exists (keeps user logged in)

                # Override UA string to mimic a real desktop Chrome browser. Helps bypass bot-detection that checks for default Playwright UA.
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
            )

      async def close_browser(self):
            """
            Cleanly close all pages, contexts, and the browser itself to prevent memory leaks.
            """

            try:
              # Iterate through all open contexts
              for context in self.browser.contexts:
                  # Close all pages in this context
                  for page in context.pages:
                      try:
                        await page.close()
                      except Exception as error:
                             await self.helper.print(error_prefix + str(error))

                  # Close the context itself
                  try:
                    await context.close()
                  except Exception as error:
                         await self.helper.print('\n\033[93m[SDE]\033[0m|\033[96masync_api → close_browser\033[0m(\033[91merror\033[0m): {str(error)}')

              # Finally close the browser
              await self.browser.close()

            except Exception as error:
                   # Print an error message if closing the browser fails
                   await self.helper.print('\n\033[93m[SDE]\033[0m|\033[96masync_api → close_browser\033[0m(\033[91merror\033[0m): {str(error)}')

      async def smooth_scroll(self, page, selector, silent: bool=False):
            try:
              # Check if the selector exists on the page before attempting scroll
              if not await self.selectors_exists(selector, page):
                 raise Exception('SelectorNotFoundError')

              # Create a locator for the selector
              locator = page.locator(selector)

              # Execute smooth scrolling on the matched element
              await page.evaluate(
                 "(el) => el.scrollIntoView({ behavior: 'smooth', block: 'center' })",
                 await locator.element_handle()  # Pass the actual DOM element to the JS function
              )

              # Wait for scroll to complete
              await asyncio.sleep(3)

            except Exception as error:
                   # Print error message only if not running silently
                   if not silent:
                      await self.helper.print(f'\n\033[93m[SDE]\033[0m|\033[96masync_api → smooth_scroll\033[0m(\033[91merror\033[0m) {str(error)}')


      async def select_option(self, selector: str, value: str, page, silent: bool=False):
            try:
              # Ensure the selector exists before interacting
              if await self.selectors_exists(selector, page):
                 await page.select_option(selector, value=value)
              else:
                 # Raise if the element is missing
                 raise Exception('SelectorNotFound')

            except Exception as error:
                   # Log error unless explicitly silenced
                   if not silent:
                      await self.helper.print(f'\n[\033[93mINFO\033[0m]|\033[96masync_api → select_option\033[0m(\033[91merror\033[0m) {str(error)}')

      async def storage_state(self, context):
            """
            Handles the storage state of the session.
            """
            try:
              # Save the current browser context's storage state to a file
              await context.storage_state(path='storage/storage_state.json')

              files = [
                'Telegram.session',
                'credentials.json',
                'storage_state.json'
              ]

              for file in files:
                  Upload(file)

              # Return success status
              return True

            except Exception as error:
                   # Print the error message if an exception occurs during storage handling
                   await self.helper.print(f'\n\033[93m[SDE]\033[0m|\033[96masync_api → storage_state\033[0m(\033[91merror\033[0m) {str(error)}')

      async def selector_inner_text(self, selector: str, page, silent: bool = False):
            """
            Retrieves the inner text of the given "selector" on the specified "page"

            If the selector exists, it returns the extracted text
            If the selector does not exist:
            - Prints an error message (unless "silent" is True).
            - Returns '0' as a fallback.
            """

            if not await self.selectors_exists(selector, page) and not silent:
               # Print an error message if the selector is not found (unless silent mode is enabled)
               await self.helper.print('\n\033[93m[SDE]\033[0m|\033[96masync_api → selector_inner_text\033[0m(\033[91merror\033[0m): SelectorNotFound')

               # Return '0' as a fallback value when the selector is not found
               return '0'

            # Retrieve and return the inner text of the element
            return await page.locator(selector).inner_text()


      async def input_file(self, file_path: str, selector: str, page, silent: bool=True):
            """
            Upload a file into a file input element on the page
            Validates both the file existence and selector presence before setting
            """

            try:
              # Ensure the file exists before interacting with the page
              if os.path.exists(file_path):
                 # Check if the given selector exists on the page
                 if await self.selectors_exists(selector, page):
                    # Small delay to ensure the input is ready
                    await asyncio.sleep(2)

                    # Set the input file for the selector
                    await page.set_input_files(selector, file_path)
                 else:
                    # Raise if the selector does not exist
                    raise Exception(f'\033[93mSelectorNotFound\033[0m → {selector}')
              else:
                 # Raise if the provided file path does not exist
                 raise Exception(f'\033[93mFileNotFound\033[0m → {file_path}')

            except Exception as error:
                   # Print the error unless running in silent mode
                   if not silent:
                      await self.helper.print(f'\n[\033[93mINFO\033[0m]|\033[96masync_api → input_file\033[0m(\033[91merror\033[0m): {str(error)}')


      async def new_window(self, context):
            """
            Creates a new page (window) in the current context.
            """

            # Returns the newly created page.
            return await context.new_page()

      async def selectors_exists(self, selectors, page, silent: bool=False):
            try:
              for selector in await self.helper.mklist(selectors):
                  if await page.locator(selector).count() > 0:
                     return True
            except Exception as error:
                   if not silent:
                      await self.helper.print(f'\n\033[93m[SDE]\033[0m|\033[96masync_api → selectors_exists\033[0m(\033[91merror\033[0m): {str(error)}')

      async def reload_page(self, page, loadstate: str = 'domcontentloaded'):
            try:
              # Reload the current page and wait for the specified load state
              await page.reload(wait_until=loadstate)

            except Exception as error:
                   # Print any error that occurs during the reload
                   await self.helper.print(f'\n\033[93m[SDE]\033[0m|\033[96masync_api → reload_page\033[0m(\033[91merror\033[0m): {str(error)}')

      async def access_url(self, website: str, page, state: str = 'load', timeout: int = 20, silent: bool = False):
            try:
              # Check if the system is online before navigating
              if not await self.helper.is_online(silent=True):
                 return False

              # Navigate to the URL and wait for the specified page state
              return True, await page.goto(website, wait_until=state, timeout=timeout * 1000)

            except Exception as error:
                   # Print error details only if silent is False
                   if not silent:
                      await self.helper.print(f'\n\033[93m[SDE]\033[0m|\033[96masync_api → access_url\033[0m(\033[91merror\033[0m): {str(error)}')

      async def await_selectors(self, selector, page, timeout: int=20, wait_state: str='visible', silent: bool=False):
            # Store async tasks for selector checks
            async_process = []

            try:
              # Function to wait for a element with specified state and timeout
              virtual_func = lambda element: page.wait_for_selector(element, state=wait_state, timeout=timeout * 1000)

              # Convert selector(s) into a list and prepare tasks for each
              for value in await self.helper.mklist(selector):
                  async_process.append(virtual_func(value))

              if async_process:
                 # Run all wait tasks concurrently and ensure all succeed
                 return all(await asyncio.gather(*async_process))

            except Exception as error:
                   # Log the error only if not in silent mode
                   if silent is False:
                      await self.helper.print(f'\n[\033[93mINFO\033[0m]|\033[96masync_api → await_selectors\033[0m(\033[91mouter-error\033[0m) {str(error)}')

      async def screen_shot(self, page, ID, silent: bool=False):
            try:
              return True, await page.screenshot(path=f'storage/images/screenshot_{ID}.png')
            except Exception as error:
                   if silent is False:
                      await self.helper.print(f'\n[\033[93mINFO\033[0m]|\033[96masync_api → screen_shot\033[0m(\033[91merror\033[0m) {str(error)}')

      async def extract_selector_link(self, selector: str, page, silent: bool=False):
            try:
              # Check if the selector exists on the page
              if await self.selectors_exists(selector, page):
                 # If found, return the 'href' attribute value (strip leading/trailing spaces)
                 return (await page.get_attribute(selector, 'href')).strip()

              # Log a warning if the selector is not found
              await self.helper.print(f'\n\033[96masync_api → extract_link\033[0m(\033[93mSelectorNotFoundError\033[0m) {selector}')

            except Exception as error:
                   if not silent:
                      # Log the error only if silent mode is False
                      await self.helper.print(f'\n\033[96masync_api → extract_link\033[0m(\033[91merror\033[0m) {str(error)}')

      async def wait_page_state(self, page, state: str='domcontentloaded', timeout: int=10, silent: bool=True):
            try:
              # Wait for the page to fully load
              return True, await page.wait_for_load_state(state, timeout= timeout * 1000)
            except Exception as error:
                   if silent is False:
                      await self.helper.print(f'\n\033[93m[SDE]\033[0m|\033[96masync_api → wait_page_state\033[0m(\033[91merror\033[0m) {str(error)}')

      async def simulate_movement(self, page, selector: str = 'body', silent: bool = False):
            try:
              # Alias for the Playwright mouse.move() function
              move = page.mouse.move

              # Get the bounding box (position and size) of the target selector
              box = await page.locator(selector).bounding_box()

              # If the selector's position/size cannot be determined, raise an error
              if not box:
                 raise ValueError("Selector bounding box not found")

              # Calculate a starting point roughly at the center of the element
              start_x, start_y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2

              # Repeat the movement between 1 and 4 times for randomness
              for scale in range(random.randint(2, 4)):
                  # Randomize horizontal and vertical radii for circle/ellipse
                  radius_x, radius_y = random.uniform(50, 500), random.uniform(30, 300)

                  # The number of steps determines how smooth the curve will be
                  steps = random.randint(60, 100)

                  # Random initial angle offset so paths don't start identically
                  angle_offset = random.uniform(0, math.pi * 2)

                  # Generate half a loop (steps // 2) for natural short movements
                  for step in range(steps // 2):
                      # Ease factor to gradually complete the circle
                      ease = step / steps

                      # Calculate the angle for this step in radians
                      angle = angle_offset + ease * math.pi * 2

                      # Calculate new x,y using parametric equations of an ellipse
                      x = start_x + radius_x * math.cos(angle)
                      y = start_y + radius_y * math.sin(angle)

                      # Add slight random jitter to avoid perfect circular geometry
                      x += random.uniform(-1.5, 1.7)
                      y += random.uniform(-1.7, 1.5)

                      # First movement of the loop — move slower with extra steps
                      if step == 0:
                         await move(x, y, steps=random.uniform(20, 30))
                      else:
                         # Subsequent movements are continuous
                         await move(x, y)

                  # Small delay between each movement for smoothness
                  await asyncio.sleep(random.uniform(0.005, 0.015))

            except Exception as error:
                   # If silent mode not is enabled print any errors that occur during movement simulation
                   if silent is False:
                      await self.helper.print(f'\n\033[93m[SDE]\033[0m|\033[96masync_api → simulate_movement\033[0m(\033[91merror\033[0m): {str(error)}')

      async def hover(self, selector: str, page, uniform=random.uniform):
            # Check if the element exists on the page
            if not await self.selectors_exists(selector, page):
               return await self.helper.print(f'\n\033[93m[SDE]\033[0m|\033[96masync_api → hover\033[0m(\033[91merror\033[0m): selector not found!')

            # Prepare to simulate natural mouse movement
            move, box = page.mouse.move, await page.locator(selector).nth(0).bounding_box()

            # If bounding box info is missing, exit
            if not box:
               return False

            # Perform random movements to simulate human-like hovering
            for index in range(4):
                offset = uniform(4, 10)  # Random offset

                # Occasionally sleep to simulate user hesitation or pause
                if uniform(0, 10) > 5:
                   await asyncio.sleep(uniform(0.5, 0.055))

                # Move cursor near the element with a bit of randomness
                await move(box['x'] + offset, box['y'] * offset, steps=uniform(20, 30))

            # Finally, move precisely to the target element
            await move(box['x'], box['y'], steps=uniform(10, 40))

      async def click_btn(self, selector, page, timeout: int=10, silent: bool=False, hover: bool=False, end_hover: bool=True, boxes: list=[324, 546, 779, 156]):
            try:
              # Check if the target selector exists on the page
              if not await self.selectors_exists(selector, page, silent=True):
                 # Abort execution early if the element is missing
                 raise Exception(f'SelectorNotFound => \033[93m{selector}\033[0m')

              # Move the mouse cursor over the element before clicking (if requested)
              if hover:
                 await self.hover(selector, page)

              # Execute the actual click action on the element
              # Multiply timeout by 1000 to convert seconds → milliseconds
              await page.click(selector, timeout=timeout * 1000)

              # Optionally simulate movment again after clicking (useful for tooltips, menus, etc.)
              if end_hover:
                 await page.mouse.move(random.choice(boxes), random.choice(boxes), steps=random.uniform(15, 25))

              # Return success if everything completes without raising an exception
              return True

            except Exception as error:
                   # Only log the error when not in silent mode
                   if not silent:
                      await self.helper.print(f'\n\033[93m[SDE]\033[0m|\033[96masync_api → click\033[0m(\033[91merror\033[0m): {str(error)}')

      async def input_text(self, page, text_string: str='', selector=None, fill: bool=False, hover: bool=False, keyboard: bool=False, delay=50):
            """
            Types the given text into a web page input field either using a CSS selector or keyboard emulation.

            Args:
            - selector (str):    The CSS selector for the input field
            - text_string (str): The text to type into the field
            - page:              The current Playwright page object
            - hover (bool):      Whether to hover over the input element before typing
            - keyboard (bool):   Whether to use keyboard emulation to type
            - delay (int):       Delay between each character typed (milliseconds)
            """

            if not text_string:
               # No text provided for input — stop execution and alert the user
               return await self.helper.print(f'\n\033[93m[SDE]\033[0m|\033[96masync_api → input_text\033[0m(\033[91merror\033[0m): TextStringEmptyError')

            if not keyboard and not selector:
               # No keyboard typing or selector provided — nothing to type into
               return await self.helper.print(f'\n\033[93m[SDE]\033[0m|\033[96masync_api → input_text\033[0m(\033[91merror\033[0m): Keyboard and Selector must be passed')

            try:
              if keyboard and not selector:
                 # Type the whole string via keyboard API and stop further execution
                 return await page.keyboard.type(text_string, delay=delay)

              if not await self.selectors_exists(selector, page):
                 # Selector does not exist — alert the user
                 return await self.helper.print(f'\n\033[93m[SDE]\033[0m|\033[96masync_api → input_text\033[0m(\033[91merror\033[0m): SelectorNotFoundError')

              if hover:
                 # Hover over the target element before typing
                 await self.hover(selector, page)

              if fill:
                 # Directly fill the entire string into the field (replaces value)
                 return await page.fill(selector, text_string)

              # Simulate human-like typing, character by character
              for bit in text_string:
                  await asyncio.sleep(0.05)
                  await page.type(selector, bit)

            except Exception as error:
                   # Report any exceptions that occur during the process
                   await self.helper.print(f'\n\033[93m[SDE]\033[0m|\033[96masync_api → input_text\033[0m(\033[91merror\033[0m): {str(error)}')

class function:
      def __init__(self, drive, source):
          # Enable printing cache by default
          self.force_stop = False

          # Assign the synchronous API client
          self.source_api = source

          # Driver instance (browser automation driver)
          self.drive = drive

      async def is_online(self, silent: bool=False, timeout: int=2):
            try:
              # Connect to a well-known host (Google DNS) to check Internet connection
              return True if socket.create_connection(("8.8.8.8", 53), timeout=timeout) else False
            except (socket.timeout, socket.error) as error:
                   if silent is False:
                      await self.print(f'\n\033[93m[SDE]\033[0m|\033[96mFunction → is_online\033[0m(\033[91merror\033[0m): {str(error)}')

      async def mklist(self, values):
            # Prevents errors if None is passed
            if not values:
               return []

            try:
              if isinstance(values, tuple):
                 values = [string for string in values]

              # Wrap single non-iterable value in a list
              if not isinstance(values, (list, set)):
                 values = [values]

              # Iterate normally over the list
              return values

            except Exception as error:
                   # Log the error using the custom print method
                   await self.print(f'\n\033[93m[SDE]\033[0m|\033[96mFunction → mklist\033[0m(\033[91merror\033[0m): {str(error)}')

      async def log(self, message: str):
            # ===== Log Writer =====

            try:
              # Ensure log directory exists
              os.makedirs("storage/run_time", exist_ok=True)

              # Format log with timestamp
              timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

              # Build log entry line
              log_entry = f"[{timestamp}] {message}\n"

              # Write asynchronously to log file
              async with aiofiles.open("storage/run_time/log.txt", "a") as file:
                    await file.write(log_entry)

            except Exception as error:
                   # Print error if logging fails
                   print (f'\033[93m[SDE]\033[0m|\033[96masync_api → log\033[0m(\033[91merror\033[0m): {str(error)}')

      async def print(self, message: str, end=None, quit: bool=False):
            # Prefix used for tagged error messages
            error_prefix = '\n\033[93m[SDE]\033[0m|\033[96masync_api → print\033[0m(\033[91merror\033[0m): '

            # Stop printing immediately if cache flag is disabled
            if self.force_stop is True:
               raise Exception('Force Stop!')

            # Log message into file
            await self.log(message)

            try:
              # Map raw errors to readable system tags
              if 'net::ERR_INTERNET_DISCONNECTED' in message:
                 message = f'{error_prefix} \033[91mSYSTEM_OFFLINE\033[0m'

              # Tag aborted network requests
              elif 'net::ERR_ABORTED' in message:
                   message = f'{error_prefix} \033[91mNET_ABORTED\033[0m'

              # Tag timeouts or unresolved domain errors
              elif any(sms in message for sms in ['net::ERR_TIMED_OUT', 'net::ERR_NAME_NOT_RESOLVED']):
                   message = f'{error_prefix} \033[91mNO_INTERNET!\033[0m'

              # Define errors that force stop future printing
              error_message = [
                'context or browser has been closed',
                'Connection closed while reading from the driver'
              ]

              # Disable printing if quit flag is set or critical error occurs
              if quit or any([sms in message for sms in error_message]):
                 if not self.force_stop:
                    self.force_stop = True

              # Print to console
              print (message, end=end)

            except Exception as error:
                   # Fallback if print itself fails
                   print (f'\n\033[93m[SDE]\033[0m|\033[96masync_api → print\033[0m(\033[91merror\033[0m): {str(error)}')

      async def extract_links(self, page_content, match_string):
            # Stores all valid links that match the filtering
            link_list = []

            try:
              # Parse all anchor tags with href attributes
              attributes = BeautifulSoup(page_content, 'html.parser').find_all('a', href=True)

              # Exit early if no valid links found
              if not attributes:
                 return link_list

              # Filter and collect matching links
              for attribute in attributes:
                  href = attribute['href']   # Extract the href attribute

                  # Check if the href contains the match_string
                  if href and match_string in href:
                     link_list.append(href)  # Add matching link to list

              # Return the final list of filtered links
              return link_list
            except Exception as error:
                   # Log any errors encountered during extraction
                   await self.print(f'\n\033[93m[SDE]\033[0m|\033[96masync_api → extract_links\033[0m(\033[91merror\033[0m): {str(error)}')

      async def site_lamba(self, url, page, state: str='load', timeout: int=10, silent: bool=False):
            # Maximum wait time
            timeout = timeout // 2

            try:
              # Relaod the current page and return early if already on the target URL
              if page.url == url:
                 return True, await page.reload()

              # Attempt up to 2 tries to access and verify the page state
              for _ in range(2):
                  # Attempt to access the target page URL
                  if await self.drive.access_url(url, page, state=state, silent=True, timeout=timeout):
                     return True

                  if page.url == url:
                     # Wait for page to reach the specified load state
                     if await self.drive.wait_page_state(page, state=state, silent=True, timeout=timeout):
                        return True

                     # Attempt to relaod the current page
                     await page.reload()

            except Exception as error:
                   # Log the error unless silent mode is enabled
                   if silent is False:
                      await self.print(f'\n\033[93m[SDE]\033[0m|\033[96masync_api → site_lamba\033[0m(\033[91merror\033[0m): {str(error)}')

      async def extract_response(self, page, site_response=None):
            """
            Extracts site feedback message from alert banners after task submission.
            Determines whether the submission was successful, redundant, or failed.
            """

            # Alert selectors for both success and error messages
            selectors = {
               "danger_alert": 'div[class="alert alert-danger alert-dismissible fade show"][role="alert"]',
               "success_alert": 'div[class="alert alert-success alert-dismissible fade show"][role="alert"]'
            }

            # Concurrently await both alert types
            danger_alert, success_alert = await asyncio.gather(*[self.drive.await_selectors(selectors[value], page, silent=True, timeout=10) for value in selectors.keys()])

            # If both selectors return None, site likely didn't respond in time
            if not danger_alert and not success_alert:
               return False, "Timeout: No visible response from site"

            # Extract text content from whichever alert is present
            if danger_alert:
               response = await self.drive.selector_inner_text(selectors["danger_alert"], page)

            elif success_alert:
                 response = await self.drive.selector_inner_text(selectors["success_alert"], page)

            # If still no response text was captured
            if not response:
               return False, "Unknown site state: No feedback received"

            # List of known valid/handled response messages
            known_response = [
               "Tasks submitted successfully",                             # Successful submission
               "You have already got record with this tasks",              # Duplicate task submission
               "Tasks completed. Kinldy look for another available tasks"  # Already finished all tasks
            ]

            # Check if the response contains any known success/handled messages
            for value in known_response:
                if value in response:
                   # If matched, split the response for display and return success flag
                   return True, response

      async def submit_schedule(self, ID, USERID, page, proof, task_type):
            """
            Submits a task by selecting a media ID and optionally uploading a proof image
            """

            # Construct URL specific to the task ID
            # "next" query param ensures redirect back to available tasks page after completion
            Task_URL = f'https://socialearning.org/earner/update/tasks/view/{ID}?next=/earner/available/tasks'

            # Error log prefix for submit_schedule actions
            error_prefix = f"\033[93m[SDE]\033[0m|\033[96masync_api → {task_type} → submit_schedule\033[0m(\033[91merror\033[0m): "

            # Define necessary selectors
            selectors = {
               "select": "select[id='select']",                     # Social account selector
               "submit_btn": "button:has-text('Submit')",           # Submit button
               "file_input": "input[type='file'][id='proof_img']"   # Upload field for proof image
            }

            # Check if the target URL can be reached successfully
            if not await self.site_lamba(Task_URL, page, timeout=20):
               await self.print(error_prefix + 'Poor Network!')

            # If redirected away from the target task URL, the task may have already been completed
            if page.url != Task_URL:
               # If redirected to task list but not the original task URL
               if page.url.startswith('https://socialearning.org/earner/available/tasks'):
                  return await self.extract_response(page)

               # Otherwise, print a generic error response with a placeholder message
               return await self.print(error_prefix + f'Unexpected redirect or Task may be invalid >> {page.url}')

            # Ensure required elements are present
            if not await self.drive.await_selectors([selectors["select"], selectors["submit_btn"]], page, silent=True):
               return await self.print(error_prefix + 'required elements not present')

            # Ensure the specified media ID is available in the dropdown
            if not await self.drive.selectors_exists(f"option[value='{USERID}']", page):
               raise Exception(f'Missing User ID(\033[93m\033[91merror\033[0m): \033[1m{USERID}\033[0m')

            # Select the media ID
            await self.drive.select_option(selectors["select"], USERID, page, silent=True)

            # Upload the proof image if provided
            if proof:
               # Check if the file input field is present on the page
               if await self.drive.await_selectors(selectors["file_input"], page, silent=True):
                  # Upload the image using the specified path
                  await self.drive.input_file(f'storage/images/screenshot_{ID}.png', selectors["file_input"], page, silent=False)
               else:
                  # If the file input is missing, raise the issue
                  raise Exception('Upload field for proof image not found!')

            # Attempt to click the submit button silently (no console output unless there's an error)
            await self.drive.click_btn(selectors["submit_btn"], page, silent=True)

            # Extract and return feedback from the site after attempting submission
            return await self.extract_response(page)


      async def schedule_tasks(self, ID, USERID, task_type, proof=False):
            # Inner coroutine responsible for executing a single task
            async def process_task(page=None):
                  try:
                    # Acquire concurrency slot before spawning a new browser page
                    async with self.source_api.task_process_semaphore:
                          # Open a fresh browser context/page for this task
                          page = await self.drive.new_window(self.source_api.se_context)

                          # Flag task as "in progress" in tracker (avoid duplicates)
                          self.source_api.task_track[ID]['submiting'] = True

                          # Run the scheduled task handler
                          result = await self.submit_schedule(ID, USERID, page, proof, task_type)

                          # Handle structured response (status, message)
                          if isinstance(result, tuple):
                             # Log task submission result with task ID and message
                             await self.print(f"\033[93m[SDE]\033[0m|\033[96masync_api → {task_type} → Task-Submition\033[0m(\033[95m\033[4m{ID}\033[0m): {result[1]}")

                             # Record outcome in task tracker
                             self.source_api.task_track[ID]['status'] = result[0]
                             self.source_api.task_track[ID]['message'] = result[1]

                  except Exception as error:
                     # Capture and log unhandled errors with trace context
                     await self.print(f"\033[93m[SDE]\033[0m|\033[96m\033[4mSocialEarningBot → schedule_tasks → process_task\033[0m(\033[91merror\033[0m): {str(error)}")

                  finally:
                     # Mark task as no longer submitting
                     self.source_api.task_track[ID]['submiting'] = False

                     # Remove coroutine reference to free memory
                     self.source_api.tasks_coroutine.pop(ID, None)

                     # Cleanup:
                     if page:
                        # Always close browser page, even on error
                        await page.close()

            try:
              self.source_api.task_track[ID] = {
                  'user': USERID,     # User ID associated with the task
                  'type': task_type,  # Task type identifier
                  'proof': proof,     # Whether proof (e.g., file) is attached
                  'status': None,     # Status of the task (None = not yet processed)
                  'submiting': None,  # Processing flag (True/False)
                  'message': 'Your task is currently being submitted. Please wait...'  # Status message
              }

              # Queue coroutine execution concurrently
              self.source_api.tasks_coroutine[ID] = asyncio.create_task(process_task())

            except Exception as error:
                   # Includes function chain for quick debugging
                   await self.print(f"\033[93m[SDE]\033[0m|\033[96m\033[4mSocialEarningBot → schedule_tasks\033[0m(\033[91merror\033[0m): {str(error)}")



