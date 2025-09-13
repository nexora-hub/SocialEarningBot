import re
import random
import asyncio


class X:
      def __init__(self, instance):
          """
          Initializes the instance with a drive and authenticates the user
          """

          # Assign the synchronous API client
          self.instance = instance

          # Stores media-related data (if provided)
          self.account_credentials = instance.data.get("Twitter", {})

      async def start(self, context):
            """
            Executes the main automation flow, handling tasks if available
            """

            # Assign the browser automation driver to instance variables
            self.drive = self.instance.drive

            # Open a new browser page (tab) within the created context
            self.page = await self.drive.new_window(context)

            # Endpoint for fetching Twitter-specific tasks from the SocialEarning site
            self.task_endpoint = self.instance.twitter_task_endpoint

            try:
              # Initialize session components
              if await self.initialize_session():
                 # Mark session as initialized
                 self.instance.sync_twitter = True
              else:
                 # Halt automation due to invalid session
                 self.instance.sync_twitter = False

                 # Log error message indicating session initialization failed
                 await self.drive.helper.print(f"\n\033[96mTwitter → session_initialization\033[0m(\033[91merror\033[0m): Opp's something went wrong")

                 # Exit gracefully if initialization fails
                 return False

              # Chcek If no tasks are available to perform
              if not await self.is_task_available():
                 # Exit the current task check or scheduling process
                 return False

              # Extract and perform tasks, storing results in the callback list
              await self.task_extraction()

            except Exception as error:
               # Log any unexpected errors during the process
               await self.drive.helper.print(f"\n[\033[93mSDE\033[0m]|\033[96mTwitter → start\033[0m(\033[91merror\033[0m): {str(error)}")

            finally:
               # Save updated browser session state (cookies, localStorage, etc.)
               await self.drive.storage_state(context)

               # Ensure page is closed to free browser resources
               if not self.page.is_closed():
                  await self.page.close()

      async def initialize_session(self):
            """
            Mounts the Twitter session by verifying authentication and accessing the homepage
            """

            try:
              # Initialize Twitter session attributes for version v1
              if not await self.mount_credentials('v1'):
                 return False

              # Initialize session components if not already initialized
              if not self.instance.sync_twitter:
                 # Authenticate the user
                 if not await self.account_lookup():
                    return False

              # Verify access to the Home URL
              if await self.drive.helper.site_lamba(self.task_endpoint, self.page, silent=True):
                 return True  # Successfully mounted

            except Exception as error:
                   # Log any unexpected errors during the process
                   await self.drive.helper.print(f"\n[\033[93mSDE\033[0m]|\033[96mTwitter → session_initialization\033[0m(\033[91merror\033[0m): {str(error)}")

      async def account_lookup(self, prefix = f"{'=' * 26} [\033[91mALERT\033[0m] {'=' * 26}"):
            # Selectors to determine account and session state
            selectors = {
              "main": 'span[class="css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3"]:has-text("Your Account")',
              "acc_state": (
                 'span[class="css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3"]:has-text("Log in")',
                 'span[class="css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3"]:has-text("Sign up")'
              )
            }

            # Common error messages for network/session issues
            errors = {
               "net": '\n[\033[93mSDE\033[0m]|\033[96mTwitter → authentication\033[0m(\033[91merror\033[0m): internet issues',
               "session": f"\n{prefix}\n\033[4m\033[91mAccess Denied!\033[0m\033[0m Manual authentication is required — log in to your X account to proceed"
            }

            # Attempt to load account settings page to confirm session
            if not await self.drive.helper.site_lamba('https://x.com/settings/account', self.page, silent=True):
               await self.drive.helper.print(errors["net"])

            # Check both page load and authenticated state concurrently
            net, auth = await asyncio.gather(
                self.drive.await_selectors(selectors["main"], self.page, timeout=15, silent=True),
                self.drive.await_selectors('a[href="/notifications"]', self.page, timeout=15, silent=True)
            )

            # Simulate user movement before starting the task (to mimic real behavior)
            await self.drive.simulate_movement(self.page)

            # Indicates logged-in state
            if auth:
               return True  # User is authenticated and on correct page

            # Handle failure to detect expected page elements (possible network issue)
            if not net:
               await self.drive.helper.print(errors["net"])

            # Check for visible login or signup elements — signals unauthenticated session
            if await self.drive.await_selectors(selectors["acc_state"], self.page, timeout=10, silent=True):
               # Disable further Twitter processing until re-enabled externally
               self.instance.twitter_disable = True

               # Notify user that manual login is required
               await self.drive.helper.print(errors['session'])

      async def mount_credentials(self, session_key):
            """
            Initializes and validates the Twitter session by verifying Media ID and required API credentials
            """

            # Dictionary of predefined error messages for different failure scenarios
            errors = {
             "user": "username not provided",  # Error when username is missing
             "missing_data": f"Missing Twitter session data for '{session_key}' →→ Please ensure the session information is provided",  # Error when session data is missing
             "invalid_id": [
                 "Media id is invalid!",       # Error when Media ID is invalid
                 "Media id is required for your X account!"  # Error when Media ID is not provided
              ]
            }

            # Retrieve Twitter session data using the session key
            session_data = self.account_credentials.get(session_key, {})

            try:
              # Check if session data is missing
              if not session_data:
                 # Disable further Twitter processing until re-enabled externally
                 self.instance.twitter_disable = True

                 # Print error message for missing session data
                 return await self.drive.helper.print(errors["missing_data"])

              # Extract username from session data
              self.username = session_data.get('username')

              # Validate username (must exist)
              if not self.username:
                 # Disable further Twitter processing until re-enabled externally
                 self.instance.twitter_disable = True

                 # Print error message for missing username
                 return await self.drive.helper.print(errors["user"])

              # Extract media ID from session data
              self.media_id = session_data.get("media-ID")

              # Validate Media ID (must be a numeric string)
              if not self.media_id or not self.media_id.isdigit():
                 # Choose appropriate error message index based on presence of user_id
                 error_index = 0 if self.user_id else 1

                 # Disable further Twitter processing until re-enabled externally
                 self.instance.twitter_disable = True

                 # Print error message for invalid or missing Media ID
                 return await self.drive.helper.print(errors["invalid_id"][error_index])

              # All required session data passed validation
              return True

            except Exception as error:
                   # Print formatted error message if an unexpected exception occurs
                   await self.drive.helper.print(f"\n[\033[93mSDE\033[0m]|\033[96mTwitter → mount_credentials\033[0m(\033[91merror\033[0m): {str(error)}")

      async def is_task_available(self):
            # Attempt to access the home URL
            if not await self.drive.helper.site_lamba(self.task_endpoint, self.page, silent=False, timeout=20):
               # Indicates network issue
               await self.drive.helper.print('\n[\033[93mSDE\033[0m]|\033[96mTwitter → is_task_available\033[0m(\033[91merror\033[0m): Poor internet')

            # Check if the current page URL is the sign-in page
            if self.page.url == 'https://socialearning.org/sign-in':
               # Stop task execution loop due to expired session or logout
               self.instance.sync_data, self.instance.infinite_loop = False, False

               # Signal that the session has ended
               return await self.drive.helper.print(  # Print error message: user session expired or logged out
                  '\n[\033[93mSDE\033[0m]|\033[96mSocialEarning\033[0m(\033[93malert\033[0m): Detected redirection to login page — session may have expired or user was logged out'
               )

            # Check if the "AVAILABLE TASKS" span appears within 20 seconds
            if not await self.drive.await_selectors('span:has-text("AVAILABLE TASKS ")', self.page, silent=True, timeout=20):
               return False

            # Check if there are tasks available
            if await self.drive.selector_inner_text("span[class='badge bg-primary'] span", self.page) == '0':
               # Print message if no tasks are available
               return await self.drive.helper.print("[\033[93mSDE\033[0m]|\033[96mTwitter\033[0m(\033[91malert\033[0m): No tasks available!")

            # Detect if there are any executable task types (e.g., Tweet Like, Page Follow, etc.)
            if await self.detect_executable_tasks():
               return True  # Task(s) detected

      async def detect_executable_tasks(self):
            """
            Scans the current page for known Twitter task types and determines if any are executable.
            """

            # Check for the presence of each task type on the page
            for task in self.instance.twitter_task_types:
                if await self.drive.selectors_exists(f"text='{task}'", self.page):
                   # Matching tasks found'
                   return True

            return False  # No matching tasks found

      async def access_task(self, SE_task_link):
            # Verify Twitter automation & bot execution loop is enabled
            if self.instance.twitter_disable or not self.instance.infinite_loop:
               return False

            # Try navigating to the task URL and validate the page load
            if not await self.drive.helper.site_lamba(SE_task_link, self.page, silent=True):
               # If attempt fail, print a network error
               await self.drive.helper.print('\n[\033[93mSDE\0330m]|\033[96mTwitter → access_task\033[0m(\033[91mnetwork\033[0m): slow internet')

            # Extract numeric task ID from task link
            task_id = re.findall(r'\d+', SE_task_link)[0]

            # Validate the extracted task ID
            if not task_id:
               return await self.drive.helper.print('\n[\033[93mSDE\033[0m]|\033[96mTwitter → access_task\033[0m(\033[91mBadTaskId\033[0m): Invalid Task ID/Task Link')

            # If task ID has not already been processed, handle itg
            if task_id not in self.instance.task_track:
               # Execute the task_handler using the provided URL
               await self.task_handler(task_id, SE_task_link)

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

      async def task_handler(self, task_id, SE_task_link, done: bool=None):
            """
            Handles the process of viewing and performing a specific job task.

            Parameters:
            - SE_task_link (str): The URL of the job to be processed.
            - done (bool): Flag indicating whether the task has been marked as completed. Defaults to False.
            """

            # Define necessary selectors for page verification
            selectors = [
               "select[id='select']", 'button:has-text("View Job")',
               'a[target="_blank"][style="text-decoration: none;"]'
            ]

            # Common error messages for network/session issues
            errors = {
              "element": "\n[\033[93mSDE\033[0m]|\033[96mTwitter → task_handler\033[0m(\033[91mSelectorNotFound\033[0m): Task element not found",
              "TaskType": "\n[\033[93mSDE\033[0m]|\033[96mTwitter → task_handler\033[0m(\033[91mUnsupportedTask\033[0m): No worker mapped for this task type",
              "internet": "\n[\033[93mSDE\033[0m]|\033[96mTwitter → task_handler\033[0m(\033[91mConnectionError\033[0m): Poor or unstable internet connection",
            }

            # Map job task types to their respective handler functions
            task_workers = {
              'X/Tweet Like': self.tweet_like,
              'X/Tweet Views': self.tweet_views,
              'X/Page Follow': self.follow_page,
              'X/Tweet Repost': self.tweet_repost,
              'X/Tweet Comment': self.tweet_comment,
            }

            # Wait for both selectors: one for generic task elements, one for the 'TASKS DETAILS' confirmation
            async_check = await asyncio.gather(*[
               self.drive.await_selectors(selectors, self.page, timeout=15, silent=True),                        # Wait for required selectors to appear on page
               self.drive.await_selectors('p:has-text("TASKS DETAILS")', self.page, timeout=15, silent=True)     # Wait for 'TASKS DETAILS' text to ensure full page load
            ])

            # If neither check was successful, the task page likely didn't load properly
            if not any(async_check):
               return await self.drive.helper.print(errors["element"])

            # If no executable task types were detected on the page
            if not await self.detect_executable_tasks():
               return await self.instance.blacklist(SE_task_link, banned=True)

            # Extract the URL associated with the task using the selector
            twitter_link = await self.drive.extract_selector_link(selectors[2], self.page)

            # Loop through all available task types and their corresponding workers
            for task, worker in task_workers.items():
                if await self.drive.selectors_exists(f"text='{task}'", self.page):
                   break
            else:
               # No matching task type found, log error
               return await self.drive.helper.print(errors["TaskType"])

            # Validate the extracted URL
            if not twitter_link.startswith('https://x.com') and not twitter_link.startswith('https://twitter.com'):
               return await self.instance.blacklist(SE_task_link, banned=True)

            # Check if the Twitter task URL is reachable
            if not await self.drive.helper.site_lamba(twitter_link, self.page, silent=True, timeout=30):
               return await self.drive.helper.print(errors["internet"])

            # Simulate user movement before starting the task (to mimic real behavior)
            await self.drive.simulate_movement(self.page)

            try:
              # Execute the task worker function using the extracted job URL
              done = await worker() if task != 'X/Page Follow' else await worker(SE_task_link)  # Ensure awaited call
            except Exception as error:
                   # Log any exceptions raised by the worker
                   await self.drive.helper.print(f"\n[\033[93mSDE\033[0m]|\033[96mTwitter → task_handler → workers\033[0m(\033[91merror\033[0m): {self.instance.error_traceback(error)}")

            # Simulate user movement again after the task (for realism or session persistence
            await self.drive.simulate_movement(self.page)

            # Check if the task was successfully completed
            if done is True:
               # Submit the task using the stored task ID and media ID
               await self.drive.helper.schedule_tasks(task_id, self.media_id, 'Twitter')

            elif not instance(done, tuple):
               # Authenticate the user
               if not await self.account_lookup():
                  # Halt automation due to invalid session
                  self.instance.sync_twitter = False

                  # Disable further Twitter processing until re-enabled externally
                  self.instance.twitter_disable = True

      async def strict_profile(self):
            # Define necessary selector
            selector = "button span[class='css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3']:has-text('Yes, view profile')"

            for index in range(3):  # Attempt clicking the button up to 3 times
                # Wait for the button to appear; exit early if not found
                if not await self.drive.await_selectors(selector, self.page, timeout=2, silent=True):
                   return False  # Return False if the button disappears or times out

                # Click the button, hovering only on the first attempt
                await self.drive.click_btn(selector, self.page, silent=True, hover = True if index == 0 else False)

            # Return True if all clicks were successful
            return True

      async def tweet_views(self):
            """Checks for notification and search elements, simulates movement"""

            # Define necessary selectors for page
            selectors = [
                 'a[href="/notifications"]',
                 "input[placeholder='Search']"
            ]

            # Ensure required elements exist
            if not await self.drive.await_selectors(selectors, self.page, silent=True):
               return await self.drive.helper.print("\n[\033[93mSDE\033[0m]|\033[96mTwitter → tweet_views\033[0m(\033[91merror\033[0m): missing required elements")

            # Add a short delay
            await asyncio.sleep(5)

            # Simulate user movement
            await self.drive.simulate_movement(self.page)

            # Return True if everything succeeds
            return True

      async def tweet_repost(self):
            # Prefix to prepend to error messages in logs
            error_prefix = "\n[\033[93mSDE\033[0m]|\033[96mTwitter → tweet_repost\033[0m(\033[91merror\033[0m): "

            # Define necessary selectors for page verification
            selectors = [
                "input[placeholder='Search']", 'a[href="/notifications"]',
                "span[class='css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3']:has-text('Views')"
            ]

            # Define selectors for repost, undo repost, and retweet button
            repost, unrepost, retweet_btn = (
               "div[class='css-175oi2r'][data-testid='Dropdown']:has(a[href*='/quotes']) span[class='css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3']:has-text('Repost')",
               "div[class='css-175oi2r'][data-testid='Dropdown']:has(a[href*='/quotes']) span[class='css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3']:has-text('Undo repost')",
               "div[class='css-175oi2r r-1kbdv8c r-18u37iz r-1oszu61 r-3qxfft r-n7gxbd r-2sztyj r-1efd50x r-5kkj8d r-h3s6tt r-1wtj0ep r-1igl3o0 r-rull8r r-qklmqi'] button[aria-label*='reposts. Repost'] svg[class='r-4qtqp9 r-yyyyoo r-dnmrzs r-bnwqim r-lrvibr r-m6rgpd r-50lct3 r-1srniue']"
            )

            # Ensure Twitter UI is ready before proceeding
            if not await self.drive.await_selectors(selectors, self.page, timeout=20, silent=True):
               await self.drive.helper.print(error_prefix + 'poor internet')

            # Scroll the repost/retweet button into view if it exists
            await self.drive.smooth_scroll(self.page, retweet_btn)

            # Attempt to click on the repost/retweet button
            if not await self.drive.click_btn(retweet_btn, self.page, hover=True, silent=False):
               return await self.drive.helper.print(error_prefix + 'unable to click the repost/retweet button')

            # If the tweet is already reposted, skip reposting
            if await self.drive.await_selectors(unrepost, self.page, timeout=4, silent=True):
               return True
            else:
               # Otherwise, perform the repost action
               await self.drive.click_btn(repost, self.page, hover=True, silent=True)

            # Optionally click the retweet button again to confirm interaction
            await self.drive.click_btn(retweet_btn, self.page, hover=True, silent=True)

            # Confirm repost was successful
            if await self.drive.await_selectors(unrepost, self.page, timeout=4, silent=True):
               return True

      async def tweet_like(self):
            # Prefix to prepend to error messages in logs
            error_prefix = "\n[\033[93mSDE\033[0m]|\033[96mTwitter → tweet_like\033[0m(\033[91merror\033[0m): "

            # Define necessary selectors for page verification
            selectors = {
                 'main': [
                    'a[href="/notifications"]', "input[placeholder='Search']",
                    "span[class='css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3']:has-text('Views')"
                 ],

                 # Define "Like" and "Unlike" button selectors
                 "like": "article[data-testid='tweet'] button[aria-label*='Like'][role='button'][data-testid='like']",
                 "unlike": "article[data-testid='tweet'] button[aria-label*='Liked'][[role='button'][data-testid='unlike']"
            }

            # Ensure Twitter UI is ready before proceeding
            if not await self.drive.await_selectors(selectors['main'], self.page, silent=True):
               await self.drive.helper.print(errors_prefix + 'slow_internet')

            # Attempt to like the tweet
            if await self.drive.await_selectors(selectors['like'], self.page, timeout=5, silent=True):
               for index in range(2):
                   # Click the like button (hovering to ensure visibility)
                   await self.drive.click_btn(selectors['like'], self.page, silent=True, hover=True if index == 0 else False)

                   # Check if the like was successful (i.e., 'unlike' icon appears)
                   if await self.drive.await_selectors(selectors['unlike'], self.page, timeout=2, silent=True):
                      break

            # If the tweet is liked, return True
            if await self.drive.await_selectors(selectors['unlike'], self.page, timeout=5, silent=True):
               return True

      async def tweet_comment(self):
            # Prefix to prepend to error messages in logs
            error_prefix = "\n[\033[93mSDE\033[0m]|\033[96mTwitter → tweet_comment\033[0m(\033[91merror\033[0m): "

            # Choose a random predefined reply
            random_comment = random.choice([
              'Omo e tuff', 'Abeg... naso',
              'meaning?', 'that kind thing'
            ])

            # Define required selectors
            selectors = {
                "comment": {
                    "input_box": 'div[class="css-175oi2r r-1dqbpge r-13awgt0 r-18u37iz"][data-testid="tweetTextarea_0_label"]',
                    "post_comment": 'button[data-testid="tweetButtonInline"] span[class="css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3"]:has-text("Reply")'
                },

                "main": [
                    'a[href="/notifications"]',
                    "input[placeholder='Search']",
                    "span[class='css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3']:has-text('Views')"
                ],

                "thread": f'div[aria-label="Timeline: Conversation"]:has-text("{self.username}")',
                "focused_input": 'div[class="public-DraftEditorPlaceholder-root public-DraftEditorPlaceholder-hasFocus"]'
            }

            # Verify that key UI components are present to ensure page is fully loaded
            if not await self.drive.await_selectors(selectors['main'], self.page, silent=True):
               return await self.drive.helper.print(error_prefix + "key UI components not present")

            # Check concurrently if the user already commented and if the reply UI is present
            user_comment, reply_UI = await asyncio.gather(
                self.drive.await_selectors(selectors['thread'], self.page, timeout=10, silent=True),
                self.drive.await_selectors(list(selectors['comment'].values()), self.page, timeout=10, silent=True)
            )

            # Detect if the user has already commented
            if user_comment:
               return True  # No need to comment again

            if not reply_UI:
               # Can't proceed without reply UI
               return await self.drive.helper.print(error_prefix + "reply UI is not present")

            # Scroll the post comment button into view if it exists
            await self.drive.smooth_scroll(self.page, selectors['comment']['post_comment'])

            # Focus the comment input box
            for index in range(3):
                # Try to click the comment input box to focus it
                await self.drive.click_btn(selectors['comment']['input_box'], self.page, hover = True if index == 0 else False)

                # Check if the input box has focus
                if await self.drive.await_selectors(selectors['focused_input'], self.page, timeout=3, silent=True):
                   break

            else:
               # Could not focus input after multiple attempts
               return await self.drive.helper.print(error_prefix + "unable to focus comment input")

            # Type the selected comment with delay to simulate real input
            await self.drive.input_text(self.page, text_string=random_comment, hover=True, keyboard=True, delay=50)

            # Click the reply button to post the comment
            await self.drive.click_btn(selectors['comment']['post_comment'], self.page, hover=True, silent=True)

            # Check if the user's comment appears in the thread (i.e., posted successfully)
            if await self.drive.await_selectors(selectors['thread'], self.page, timeout=10, silent=True):
               return True  # Comment posted successfully

      async def user_account_lookup(self, selectors, SE_task_link, errors_prefix):
            # Perform profile strictness validation
            if await self.strict_profile():
               # If strict_profile returns True (i.e., profile restriction detected), log an appropriate error
               await self.drive.helper.print(errors_prefix + "Profile access restricted — cannot view/interact with the user profile")

            # Detect if the account is suspended → blacklist task
            elif await self.drive.selectors_exists(selectors['suspended'], self.page):
                 await self.drive.helper.print(errors_prefix + "User_account suspended")

            # Detect if the account does not exits → blacklist task
            elif await self.drive.selectors_exists(selectors['non_exist'], self.page):
                 await self.drive.helper.print(errors_prefix + "This account doesn’t exist")

            # If none of the above, account is valid
            else:
               return True

            # Blacklist the task if account is invalid/restricted
            await self.instance.blacklist(SE_task_link, banned=True)

      async def follow_page(self, SE_task_link):
            # Define necessary selectors for verifying that the Twitter UI has loaded
            selectors = {
               "main": [
                 'a[href="/notifications"]',      # Notifications link (indicates logged-in state)
                 "input[placeholder='Search']",   # Search input (used for navigation)
                 "div[class='css-146c3p1 r-bcqeeo r-qvutc0 r-37j5jr r-q4m81j r-a023e6 r-rjixqe r-b88u0q r-1awozwy r-6koalj r-18u37iz r-16y2uox r-1777fci']"  # Page anchor content
               ],

               "non_exist": 'span[class="css-1jxf684 r-bcqeeo r-1ttztb7 r-qvutc0 r-poiln3"]:has-text("This account doesn’t exist")',
               "suspended": 'div[class="css-175oi2r"] div[data-testid="empty_state_body_text"]:has-text("X suspends accounts which violate the")'
            }

            # Error log prefix for Twitter follow actions
            errors_prefix = "\n[\033[93mSDE\033[0m]|\033[96mTwitter → follow\033[0m(\033[91merror\033[0m): "

            # Ensure Twitter profile page is fully loaded
            if not await self.drive.await_selectors(selectors['main'], self.page, silent=True):
               # Stop if essential UI components are missing
               return await self.drive.helper.print(errors_prefix + "Required UI elements not found")

            # Validate target account (restricted / suspended / non-existent)
            if not await self.user_account_lookup(selectors, SE_task_link, errors_prefix):
               return False, False

            # Extract the username (e.g., '@elonmusk') from the browser page title
            target_username = re.findall(r'\@.*?\)', await self.page.title())

            # If the username could not be extracted, return failure
            if not target_username:
               return await self.drive.helper.print(errors_prefix + "target-username extraction faild")

            # Remove the closing parenthesis from the extracted username
            target_username = target_username[0][:-1]

            # Define the dynamic selectors for "Follow" and "Following" buttons
            follow, following = [
               f"button[aria-label='Follow {target_username}']",
               f"button[aria-label='Following {target_username}']"
            ]

            # Try up to 3 times to click the "Follow" button if it's visible
            if await self.drive.await_selectors(follow, self.page, timeout=5, silent=True):
               for index in range(3):  # Retry logic with hover only on the first attempt
                   await self.drive.click_btn(follow, self.page, hover=(index == 0), silent=True)

                   # Break early if "Following" button appears (follow was successful)
                   if await self.drive.selectors_exists(following, self.page, silent=True):
                      break

                   # Wait a bit longer between retries (0.5s, 1s, 1.5s)
                   await asyncio.sleep(0.5 * (index + 1))

            # Final check: confirm user was successfully followed
            if await self.drive.await_selectors(following, self.page, silent=True):
               return True  # Follow succeeded

            return False  # Follow failed

      async def demo(self):
            url = 'https://x.com/koto_bi?t=sG34PMWO2sjsz9YIE04ndg&s=09'
            await self.drive.helper.site_lamba(url, self.page, silent=True)
            print (await self.follow_page(url))
