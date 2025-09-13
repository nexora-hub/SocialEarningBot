import re
import random
import asyncio


class IG:
      def __init__(self, instance):
          """
          Initializes the instance with a drive and authenticates the user
          """

          # Assign the synchronous API client
          self.instance = instance

          # Stores media-related data (if provided)
          self.account_credentials = instance.data.get("Instagram", {})

      async def start(self, context):
            """
            Executes the main automation flow, handling tasks if available
            """

            # Assign the browser automation driver from the main instance
            self.drive = self.instance.drive

            # Open a new browser page (tab) within the created context
            self.page = await self.drive.new_window(context)

            # Endpoint for fetching Instagram-specific tasks
            self.task_endpoint = self.instance.instagram_task_endpoint

            try:
              # Initialize session (cookies, state, login checks, etc.)
              if await self.session_initialization():
                 # Mark Instagram session as successfully synced
                 self.instance.sync_instagram = True
              else:
                 # Mark session as invalid → automation should not continue
                 self.instance.sync_instagram = False

                 # Log error message indicating session initialization failed
                 await self.drive.helper.print(f"\033[93m[SDE]\033[0m|\033[96mInstagram → session_initialization\033[0m(\033[91merror\033[0m): Opp's something went wrong")

                 # Exit early due to failed initialization
                 return False

              # Check if there are no tasks available for Instagram
              if not await self.is_task_available():
                 # Exit early if nothing to process
                 return False

              # Extract and perform tasks (results handle internally)
              await self.task_extraction()

            except Exception as error:
               # Catch and log any unexpected errors during execution
               await self.drive.helper.print(f"\033[93m[SDE]\033[0m|\033[96mInstagram → start\033[0m(\033[91merror\033[0m): {str(error)}")

            finally:
               # Save updated browser session state (cookies, localStorage, etc.)
               await self.drive.storage_state(context)

               # Ensure the Playwright page is closed to free resources
               if not self.page.is_closed():
                  await self.page.close()

      async def session_initialization(self):
            """
            Mounts the Instagram session by verifying authentication and accessing the homepage
            """

            try:
              # Initialize Instagram session attributes for version v1
              if not await self.mount_credentials('v1'):
                 return False

              # Initialize session components if not already initialized
              if not self.instance.sync_instagram:
                 # Authenticate the user
                 if not await self.account_lookup():
                    return False

              # Access to the Home URL & # Successfully mounted
              return True, await self.drive.helper.site_lamba(self.task_endpoint, self.page, silent=True)

            except Exception as error:
                   # Log any unexpected errors during the process
                   await self.drive.helper.print(f"\033[93m[SDE]\033[0m|\033[96mInstagram → session_initialization\033[0m(\033[91merror\033[0m): {str(error)}")

      async def mount_credentials(self, session_key):
            """
            Initializes and validates the Instagram session by verifying Media ID and required API credentials
            """

            # Prefix used for logging errors in a formatted style
            prefix = '\n[\033[93mSDE\033[0m]|\033[96mInstagram → mount_session_credentials\033[0m(\033[91merror\033[0m): '

            # Dictionary of predefined error messages for different failure scenarios
            errors = {
             "user": "username not provided",                 # Error when username is missing
             "missing_data": f"Missing Instagram session data for '{session_key}' →→ Please ensure the session information is provided",  # Error when session data is missing
             "invalid_id": [
                 "Media id is invalid!",                      # Error when Media ID is invalid
                 "Media id is required for your IG account!"  # Error when Media ID is not provided
              ]
            }

            try:
              # Retrieve session data for Facebook using the provided session key
              session_data = self.account_credentials.get(session_key, {})

              # Validate that session data exists; if missing, log an error and exit early
              if not session_data:
                 # Disable further Instagram processing until re-enabled externally
                 self.instance.instagram_disable = True

                 return await self.drive.helper.print(prefix + errors["missing_data"])

              # Extract username from the session data
              self.username = session_data.get('username')

              # Ensure username is present; if missing, log an error and exit early
              if not self.username:
                 # Disable further Instagram processing until re-enabled externally
                 self.instance.instagram_disable = True

                 return await self.drive.helper.print(prefix + errors["user"])

              # Extract Media ID from the session data
              self.media_id = session_data.get("media-ID")

              # Validate Media ID (must be an integer)
              if  not self.media_id or not self.media_id.isdigit():
                 # Decide which error message to use based on whether a user_id exists
                 error_index = 0 if self.user_id else 1

                 # Disable further Instagram processing until re-enabled externally
                 self.instance.instagram_disable = True

                 # Return an alert message for invalid or missing Media ID
                 return await self.drive.helper.print(prefix + errors["invalid_id"][error_index])

              # If all checks pass, session credentials are valid
              return True

            except Exception as error:
                   # Catch and log any unexpected runtime errors during credential mounting
                   await self.drive.helper.print(
                      f"\033[93m[SDE]\033[0m|\033[96mInstagram → mount_session_credentials\033[0m(\033[91merror\033[0m): {str(error)}"
                   )

      async def account_lookup(self, prefix=f"{'=' * 26} [\033[91mALERT\033[0m] {'=' * 26}"):
            # Selectors to determine account and session state
            selectors = {
               "main": 'h2[dir="auto"]:has-text("Edit profile")',
               "login": [
                 'button[type="submit"]:has-text("Log in")',
                 'input[aria-label="Phone number, username, or email"][name="username"]'
               ]
            }

            # Common error messages for network/session issues
            errors = {
               "network_error": '\033[93m[SDE]\033[0m|\033[96mInstagram → authentication\033[0m(\033[91merror\033[0m): internet issues',
               "session_error": f"\n{prefix}\n\033[4m\033[91mAccess Denied!\033[0m\033[0m Manual authentication is required — log in to your IG account to proceed\n"
            }

            # Attempt to load account settings page to confirm session
            if not await self.drive.helper.site_lamba('https://www.instagram.com/accounts/edit/', self.page, silent=True, timeout=20):
               await self.drive.helper.print(errors["network_error"])  # Print network error if page fails to load

            # Simulate user movement before starting the task (to mimic real behavior)
            await self.drive.simulate_movement(self.page)

            # Check both page load and authenticated state concurrently
            auth = await asyncio.gather(
                self.drive.await_selectors(selectors["main"], self.page, timeout=15, silent=True),         # Wait for main page selector
                self.drive.await_selectors('a[href="/direct/inbox/"]', self.page, timeout=15, silent=True) # Wait for inbox link selector
            )

            # If still on account settings page, consider session valid
            if any(auth) or self.page.url.startswith('https://www.instagram.com/accounts/edit/'):
               return True  # User is authenticated

            # List of endpoints that indicate authentication challenges or login pages
            auth_endpoints = [
               'https://www.instagram.com/challenge/',
               'https://www.instagram.com/accounts/login'
            ]

            # Check if current page URL matches any auth endpoint or if login elements are visible (indicating an unauthenticated session)
            if any([self.page.url.startswith(links) for links in auth_endpoints]) or await self.drive.await_selectors(selectors["login"], self.page, timeout=10, silent=True):
               # Disable further Instagram processing until re-enabled externally
               self.instance.instagram_disable = True

               # Inform the user that manual login is required
               await self.drive.helper.print(errors['session_error'])

      async def is_task_available(self):
            # Attempt to access the task end point
            if not await self.drive.helper.site_lamba(self.task_endpoint, self.page, silent=False, timeout=20):
               # Indicates network issue
               await self.drive.helper.print('\033[93m[SDE]\033[0m|\033[96mInstagram → is_task_available\033[0m(\033[91merror\033[0m): Poor internet')

            # Chcek if redirected to login page (session expired / logged out)
            if self.page.url.startswith('https://socialearning.org/sign-in'):
               # Stop task execution loop due to expired session or logout
               self.instance.sync_data, self.instance.infinite_loop = False, False

               # Signal that the session has ended
               return await self.drive.helper.print(  # Print error message: user session expired or logged out
                  '\033[93m[SDE]\033[0m|\033[96mSocialEarning\033[0m(\033[93malert\033[0m): Detected redirection to login page — session may have expired or user was logged out'
               )

            # Check if the "AVAILABLE TASKS" span appears within 20 seconds
            if not await self.drive.await_selectors('span:has-text("AVAILABLE TASKS ")', self.page, silent=True, timeout=20):
               return False

            # Check if there are tasks available
            if await self.drive.selector_inner_text("span[class='badge bg-primary'] span", self.page) == '0':
               # Print message if no tasks are available
               return await self.drive.helper.print("[\033[93mSDE\033[0m]|\033[96mInstagram\033[0m(\033[91malert\033[0m): No tasks available!")

            # Detect if there are any executable task types (e.g., Post Like, Page Follow, etc.)
            if await self.detect_executable_tasks():
               return True  # Task(s) detected

      async def detect_executable_tasks(self):
            """
            Scans the current page for known Instagram task types and determines if any are executable
            """

            # Check for the presence of each task type on the page
            for task in self.instance.instagram_task_types:
                if await self.drive.selectors_exists(f"text='{task}'", self.page):
                   # Matching tasks found
                   return True

            # No matching tasks found
            return False

      async def task_extraction(self):
            # Retry loop to check for new tasks twice
            for _ in range(2):
                # Extract task links from current page HTML
                for links in await self.drive.helper.extract_links(await self.page.content(), 'next=/earner/available/'):
                    # Skip if link is blacklisted
                    if await self.instance.blacklist(f'https://socialearning.org{links}'):
                       continue

                    # Verify homepage is loaded before proceeding
                    if await self.drive.helper.site_lamba(self.task_endpoint, self.page, silent=True):
                       # Access task if link element exists on the page
                       if await self.drive.selectors_exists(f"a[href='{links}']", self.page):
                          await self.access_task(f'https://socialearning.org{links}')

                    # Handle missing "AVAILABLE TASKS" indicator
                    elif not await self.drive.await_selectors('span:has-text("AVAILABLE TASKS ")', self.page, timeout=10):
                         await self.drive.helper.print(f"\n\033[96mInstagram → view_task\033[0m(\033[91merror\033[0m): Required UI elements not found!")

                    # Exit loop if automation is stopped
                    if not self.instance.infinite_loop:
                       break

      async def access_task(self, SE_task_link):
            # Verify Instagram automation & bot execution loop is enabled
            if self.instance.instagram_disable or not self.instance.infinite_loop:
               return False

            # Try navigating to the task URL and validate the page load
            if not await self.drive.helper.site_lamba(SE_task_link, self.page, silent=True):
               # If attempt fail, print a network error
               await self.drive.helper.print('\n[\033[93mSDE\0330m]|\033[96mInstagram → access_task\033[0m(\033[91mnetwork\033[0m): slow internet')

            # Extract numeric task ID from task link
            task_id = re.findall(r'\d+', SE_task_link)[0]

            # Validate the extracted task ID
            if not task_id:
               return await self.drive.helper.print('\n[\033[93mSDE\033[0m]|\033[96mInstagram → access_task\033[0m(\033[91mBadTaskId\033[0m): Invalid Task ID/Task Link')

            # If task ID has not already been processed, handle itg
            if task_id not in self.instance.task_track:
               # Execute the task_handler using the provided URL
               await self.task_handler(task_id, SE_task_link)

      async def task_handler(self, task_id, SE_task_link, done: bool=None):
            """
            Handles the process of viewing and performing a specific job task

            Parameters:
            - SE_task_link (str): The URL of the job to be processed
            - done (bool): Flag indicating whether the task has been marked as completed, Defaults to False
            """

            # Define necessary selectors for page verification
            selectors = [
               'select[id="select"]', 'button:has-text("View Job")',
               'a[target="_blank"][style="text-decoration: none;"]'
            ]

            # Map job task types to their respective handler functions
            task_workers = {
              'INSTAGRAM/Post Like': self.post_like,
              'INSTAGRAM/Page Follow': self.page_follow,
              'INSTAGRAM/Post Comment': self.post_comment
            }

            # Wait for both selectors: one for generic task elements, one for the 'TASKS DETAILS' confirmation
            async_check = await asyncio.gather(*[
               self.drive.await_selectors(selectors, self.page, timeout=15, silent=True),                        # Wait for required selectors to appear on page
               self.drive.await_selectors('p:has-text("TASKS DETAILS")', self.page, timeout=15, silent=True)     # Wait for 'TASKS DETAILS' text to ensure full page load
            ])

            # If neither check was successful, the task page likely didn't load properly
            if not any(async_check):
               return False

            # If no executable task types were detected on the page
            if not await self.detect_executable_tasks():
               return await self.instance.blacklist(SE_task_link, banned=True)

            # Extract the URL associated with the task using the selector
            instagram_link = await self.drive.extract_selector_link(selectors[2], self.page)

            # Loop through all available task types and their corresponding workers
            for task, worker in task_workers.items():
                if await self.drive.selectors_exists(f"text='{task}'", self.page):
                   break
            else:
               return False

            # Validate the extracted URL
            if not instagram_link.startswith('https://www.instagram.com') and not instagram_link.startswith('https://instagram.com'):
               return await self.instance.blacklist(SE_task_link, banned=True)

            # Check if the Instagram task URL is reachable
            if not await self.drive.helper.site_lamba(instagram_link, self.page, silent=True, timeout=30):
               return await self.drive.helper.print(f"\n[\033[93mSDE\033[0m]|\033[96mInstagram → task_handler\033[0m(\033[91merror\033[0m): Poor Internet")

            # Simulate user movement before starting the task (to mimic real behavior)
            await self.drive.simulate_movement(self.page)

            try:
              # Execute the task worker function
              done = await worker() if task != 'INSTAGRAM/Page Follow' else await worker(SE_task_link)
            except Exception as error:
                   # Log any exceptions raised by the worker
                   await self.drive.helper.print(f"\n[\033[93mSDE\033[0m]|\033[96mInstagram → task_handler → workers\033[0m(\033[91merror\033[0m): {str(error)}")

            # Simulate user movement again after task completion (for realism)
            await self.drive.simulate_movement(self.page)

            # Check if the task was successfully completed
            if done:
               # Submit the task using the stored task ID and media ID
               await self.drive.helper.schedule_tasks(task_id, self.media_id, 'Instagram')

            elif not isinstance(done, tuple):
                 # Authenticate the user
                 if not await self.account_lookup():
                    # Halt automation due to invalid session
                    self.instance.sync_instagram = False

                    # Disable further Instagram processing until re-enabled externally
                    self.instance.instagram_disable = True

      async def page_follow(self, SE_task_link):
            # Prefix to prepend to error messages in logs
            error_prefix = "\n[\033[93mSDE\033[0m]|\033[96mInstagram → post_follow\033[0m(\033[91merror\033[0m): "

            # Define necessary selectors for verifying that the Instagram UI has loaded
            selectors = {
               "main": [
                   'a[href="/direct/inbox/"]',  # Direct message inbox link
                   'svg[aria-label="Options"]:has-text("Options")',  # Selector for the "Options" icon with aria-label
                   'header[class="xrvj5dj xl463y0 x1ec4g5p xdj266r xwy3nlu xh8yej3"] div[class="x6s0dn4 x78zum5 x1q0g3np xs83m0k xeuugli x1n2onr6"]'  # Page anchor content
               ],
               "dialog": 'div[role="dialog"] div[class="x6s0dn4 x78zum5 xdt5ytf x1p5oq8j x2b8uid"] div[role="button"]:has-text("Not now")'
            }

            # Define the dynamic selectors for "Follow" and "Following" buttons
            follow, following = [
               'button[class=" _aswp _aswr _aswu _asw_ _asx2"] div[class="_ap3a _aaco _aacw _aad6 _aade"]:has-text("Follow")',
               'button[class=" _aswp _aswr _aswv _asw_ _asx2"] div[class="_ap3a _aaco _aacw _aad6 _aade"]:has-text("Following")'
            ]

            # Ensure Instagram page has fully loaded before proceeding
            if not await self.drive.await_selectors(selectors['main'], self.page, silent=True, timeout=15):
               # Check if the page is unavailable or just missing UI components
               if await self.drive.selectors_exists("text='Sorry, this page isn\'t available.'", self.page):
                  # Mark user as banned
                  await self.instance.blacklist(SE_task_link, banned=True)

                  # Log failure reason and exit
                  return False, await self.drive.helper.print(error_prefix + 'Instagram user-page unavailable')

               # Log failure reason and exit
               return await self.drive.helper.print(error_prefix + 'Required UI elements not found')

            # If a "Not now" dialog is present, dismiss it
            if await self.drive.selectors_exists(selectors['dialog'], self.page, silent=True):
               await self.drive.click_btn(selectors['dialog'], self.page, silent=True)

            # Try up to 3 times to click the "Follow" button if it's visible
            if await self.drive.await_selectors(follow, self.page, timeout=5, silent=True):
               for index in range(3):  # Retry logic with hover only on the first attempt
                   await self.drive.click_btn(follow, self.page, silent=True, hover = True if index == 0 else False)

                   # Break early if "Following" button appears (follow was successful)
                   if await self.drive.selectors_exists(following, self.page, silent=True):
                      break

                   # Wait a bit longer between retries (0.5s, 1s, 1.5s)
                   await asyncio.sleep(0.5 * (index + 1))

            # Final check: confirm user was successfully followed
            if await self.drive.await_selectors(following, self.page, silent=True):
               return True  # Follow succeeded

      async def post_comment(self):
            # Prefix to prepend to error messages in logs
            error_prefix = "\n[\033[93mSDE\033[0m]|\033[96mInstagram → post_comment\033[0m(\033[91merror\033[0m): "

            # Choose a random predefined reply
            random_comment = random.choice(['swears',
              'Omo e tuff', 'Abegy... naso',
              'Meaning?', 'That kind thing'
            ])

            # Define required selectors
            selectors = {
                "main": [
                  'a[href="/direct/inbox/"]',                                # Direct message inbox link
                  'svg[aria-label="More options"]:has-text("More options")'  # Selector for the "Options" icon with aria-label
                ],

                "comment": {
                   "input_box": "textarea[aria-label='Add a comment…'][placeholder='Add a comment…']",      # Comment input box
                   "post_comment": 'form[method="POST"] div[role="button"][tabindex="0"]:has-text("Post")'  # Post button
                },

                "focused_input": 'textarea[aria-label="Add a comment…"][placeholder="Add a comment…"][data-focus-visible-added=""]',
                "thread": f'span[class="xt0psk2"] span[class="_ap3a _aaco _aacw _aacx _aad7 _aade"][dir="auto"]:has-text("{self.username}")'
            }

            # Await both key components and existing user comment
            components, user_comment = await asyncio.gather(
               self.drive.await_selectors(selectors['main'], self.page, silent=True, timeout=10),
               self.drive.await_selectors(selectors['thread'], self.page, silent=True, timeout=10)
            )

            # Detect if the user has already commented
            if user_comment:
               return True  # No need to comment again

            # Stop if page isn’t fully loaded
            if not components:
               return await self.drive.helper.print(error_prefix + "key UI components not present")

            # Ensure comment box exists
            if not await self.drive.await_selectors(selectors['comment']["input_box"], self.page, timeout=10, silent=True):
               return await self.drive.helper.print(error_prefix + "reply UI is not present")

            # Focus the comment input box
            for index in range(3):
                # Try to click the comment input box to focus it
                await self.drive.click_btn(selectors['comment']['input_box'], self.page, silent=True, hover = True if index == 0 else False)

                # Check if the input box has focus
                if await self.drive.await_selectors(selectors['focused_input'], self.page, silent=True, timeout=2):
                   break

            else:
               # Could not focus input after multiple attempts
               return await self.drive.helper.print(error_prefix + "unable to focus comment input")

            # Type the selected comment with delay to simulate real input
            await self.drive.input_text(self.page, selector=selectors['comment']['input_box'], text_string=random_comment, hover=True)

            # Click the reply button to post the comment
            await self.drive.click_btn(selectors['comment']['post_comment'], self.page, hover=True, silent=True)

            # Check if the user's comment appears in the thread (i.e., posted successfully)
            if await self.drive.await_selectors(selectors['thread'], self.page, timeout=10, silent=True):
               return True  # Comment posted successfully

      async def post_like(self):
            # Prefix to prepend to error messages in logs
            error_prefix = "\n[\033[93mSDE\033[0m]|\033[96mInstagram → post_like\033[0m(\033[91merror\033[0m): "

            # Define necessary selectors for page verification
            selector = {
               "main": [
                  'a[href="/direct/inbox/"]',                                # Direct message inbox link
                  'svg[aria-label="More options"]:has-text("More options")'  # Selector for the "Options" icon with aria-label
               ],
               "like": 'div[role="button"] svg[aria-label="Like"][height="24"]:has-text("Like")',
               "unlike": 'div[role="button"] svg[aria-label="Unlike"][height="24"]:has-text("Unlike")'
            }

            # Ensure Instagram UI is ready before proceeding
            if not await self.drive.await_selectors(selector['main'], self.page, silent=True):
               await self.drive.helper.print(error_prefix + 'slow_internet')

            # Attempt to like the tweet
            if await self.drive.await_selectors(selector['like'], self.page, timeout=5, silent=True):
               # Scroll the like button into view if it exists
               await self.drive.smooth_scroll(self.page, selector['like'])

               for index in range(3):
                   # Click the like button (hovering to ensure visibility)
                   await self.drive.click_btn(selector['like'], self.page, silent=True, end_hover=False, hover=True if index == 0 else False)

                   # Check if the like was successful (i.e., 'unlike' icon appears)
                   if await self.drive.await_selectors(selector['unlike'], self.page, timeout=2, silent=True):
                      break

            # If the post is liked, return True
            if await self.drive.await_selectors(selector['unlike'], self.page, timeout=5, silent=True):
               return True

      async def demo(self):
            url = 'https://www.instagram.com/reel/DN_Xhu6gvZa/?igsh=MTVnZGhjOWY4eHJxag=='
            await self.drive.helper.site_lamba(url, self.page, silent=True)
            print (await self.post_like(url))

