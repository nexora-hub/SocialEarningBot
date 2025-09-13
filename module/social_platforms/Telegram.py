import re
import asyncio

from telethon import TelegramClient
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

class TG:
      def __init__(self, instance):
          """
          Initializes Telegram automation with drive, media data, and ban handler
          """

          # Telegram client instance placeholder
          self.client = None

          # Extract Telegram-specific media data
          self.media_data = instance.data.get("Telegram", {})

          # Assign the synchronous API client
          self.instance = instance

      async def start(self, context):
            """
            Executes the main automation flow, handling tasks if available
            """

            # Assign the browser automation driver to instance variables
            self.drive = self.instance.drive

            # Open a new browser page (tab) within the created context
            self.page = await self.drive.new_window(context)

            # Endpoint for fetching Telegram-specific tasks from the SocialEarning site
            self.task_endpoint = self.instance.telegram_task_endpoint

            try:
              # Initialize session components
              if await self.initialize_session():
                 # Mark session as initialized
                 self.instance.sync_telegram = True
              else:
                 # Halt automation due to invalid session
                 self.instance.sync_telegram = False

                 # Log error message indicating session initialization failed
                 await self.drive.helper.print(f"\033[96mTelegram → session_initialization\033[0m(\033[91merror\033[0m): Opp's something went wrong")

                 # Exit gracefully if initialization fails
                 return False

              # Chcek If no tasks are available to perform
              if not await self.is_task_available():
                 # Exit the current task check or scheduling process
                 return False

              # Detect if there are any executable task types (e.g., Group, Channel, etc.)
              if not await self.detect_executable_tasks():
                 # Ensure function exits properly after execution
                 return False

              # Extract and perform tasks, storing results in the callback list
              await self.task_extraction()

            except Exception as error:
               # Log any exceptions that occur during task execution
               await self.drive.helper.print(f"[\033[93mSDE\033[0m]|\033[96mTelegram → start\033[0m(\033[91merror\033[0m): {str(error)}")

            finally:
               # Save updated browser session state (cookies, localStorage, etc.)
               await self.drive.storage_state(context)

               # Ensure page is closed to free browser resources
               if not self.page.is_closed():
                  await self.page.close()

               # Gracefully disconnect client if session was synced
               if self.client and self.instance.sync_telegram:
                  await self.client.disconnect()

      async def initialize_session(self):
            """
            Initializes and validates the Telegram session by verifying Media ID and required API credentials
            """

            # Retrieve the phone number
            phone_number = self.media_data.get('Phone')

            # Check if phone number is missing
            if not phone_number:
               # Disable further Telegram processing until re-enabled externally
               self.instance.telegram_disable = True

               # Display an alert message for missing phone_number
               return await self.drive.helper.print(f"\n{'-' * 26}[\033[91mALERT\033[0m]{'-' * 26}\nPhone number is required to proceed with Telegram Task")

            # Retrieve the media ID
            self.media_id = self.media_data.get("media-ID")

            # Validate Media ID (must be a numeric string)
            if not self.media_id or not str(self.media_id).isdigit():
               # Determine the appropriate alert message
               alert_msg = "Telegram Media ID is invalid!" if self.media_id else "Media ID is required for your Telegram account!"

               # Display an alert message for invalid or missing Media ID
               await self.drive.helper.print(f"\n{'-' * 26}[\033[91mALERT\033[0m]{'-' * 26}\n{alert_msg}")

               # Disable further Telegram processing until re-enabled externally
               self.instance.telegram_disable = True

            # Telegram app credentials
            self.API_ID = self.media_data.get('API_ID')
            self.API_Hash = self.media_data.get('API_Hash')

            # Check if any required credential is missing
            if not all([self.API_ID, self.API_Hash]):
               # Disable further Telegram processing until re-enabled externally
               self.instance.telegram_disable = True

               return await self.drive.helper.print(  # Display an alert message for missing API credentials
                  f"\n{'-' * 26}[\033[91mALERT\033[0m]{'-' * 26}\nTelegram error: Missing one or more API credentials. Please ensure all tokens and keys are set correctly in your media configuration"
               )

            # Initialize session components if not already initialized
            if not self.instance.sync_telegram:
               # If authenticated, initialize
               if not await self.account_lookup():
                  # Exit gracefully if initialization fails
                  return False

            # Create a new Telegram client instance with local session storage
            self.client = TelegramClient('storage/Telegram', self.API_ID, self.API_Hash)

            # Return True and Start the Telegram client using the provided phone number and return
            return True, await self.client.start(phone_number)

      async def account_lookup(self, timeout: int=15):
            """
            Checks if the Telegram session is logged in by validating presence of expected elements.
            """

            # Define necessary selectors
            selector = 'span[class="tgme_action_button_label"]:has-text("Open in Web")'

            # Try accessing a known channel
            if not await self.drive.helper.site_lamba('https://t.me/org_nexora', self.page, timeout=timeout, silent=True):
               # Indicates network issue
               await self.drive.helper.print('[\033[93mSDE\033[0m]\033[96mTelegram → authenticate_session\033[0m(\033[91merror\033[0m): Poor Internet')

            # Ensure required UI elements are present
            if await self.drive.await_selectors(selector, self.page, silent=True, timeout=timeout):
               # Return success
               return True

            # Disable further Telegram processing until re-enabled externally
            self.instance.telegram_disable = True

            # Print an alert message indicating access is denied due to not being logged in
            await self.drive.helper.print(f"\n{('-' * 26)}[\033[91mALERT\033[0m]{('-' * 26)}\n\033[4m\033[91maccess_denied!\033[0m Please sign into your Teleram account to proceed")

      async def is_task_available(self):
            # Attempt to access the home URL
            if not await self.drive.helper.site_lamba(self.task_endpoint, self.page, silent=True, timeout=20):
               # Indicates network issue
               await self.drive.helper.print('\033[96mTelegram → is_task_available\033[0m(\033[91merror\033[0m): Poor internet')

            # Chcek if redirected to login page (session expired / logged out)
            if self.page.url.startswith('https://socialearning.org/sign-in'):
               # Stop task execution loop due to expired session or logout
               self.instance.sync_data, self.instance.infinite_loop = False, False

               # Signal that the session has ended
               return await self.drive.helper.print(  # Print error message: user session expired or logged out
                  '[\033[93mSDE\033[0m]|\033[96mSocialEarning\033[0m(\033[93malert\033[0m): Detected redirection to login page — session may have expired or user was logged out'
               )

            # Check if the "AVAILABLE TASKS" span appears within 20 seconds
            if not await self.drive.await_selectors('span:has-text("AVAILABLE TASKS ")', self.page, silent=True, timeout=20):
               return False

            # Check if there are tasks available
            if await self.drive.selector_inner_text("span[class='badge bg-primary'] span", self.page) == '0':
               # Print message if no tasks are available
               return print ("\033[96mTelegram\033[0m(\033[91malert\033[0m): No tasks available!")

            # Task(s) detected
            return True

      async def detect_executable_tasks(self):
            """
            Scans the current page for known Telegram task types and determines if any are executable
            """

            # Check for the presence of each task type on the page
            for task in self.instance.telegram_task_types:
                if await self.drive.selectors_exists(f"text='{task}'", self.page):
                   return True # Matching tasks found

            return False  # No matching tasks found

      async def access_task(self, SE_task_link):
            # Verify Telegram automation & bot execution loop is enabled
            if self.instance.telegram_disable or not self.instance.infinite_loop:
               return False

            # Try navigating to the task URL and validate the page load
            if not await self.drive.helper.site_lamba(SE_task_link, self.page, silent=True):
               # If attempt fail, print a network error
               await self.drive.helper.print('[\033[93mSDE\0330m]|\033[96mTelegram → access_task\033[0m(\033[91mnetwork\033[0m): slow internet')

            # Extract numeric task ID from task link
            task_id = re.findall(r'\d+', SE_task_link)[0]

            # Validate the extracted task ID
            if not task_id:
               return await self.drive.helper.print('[\033[93mSDE\033[0m]|\033[96mTelegram → access_task\033[0m(\033[91mBadTaskId\033[0m): Invalid Task ID/Task Link')

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
                         await self.drive.helper.print(f"\033[96mInstagram → view_task\033[0m(\033[91merror\033[0m): Required UI elements not found!")

                    # Exit loop if automation is stopped
                    if not self.instance.infinite_loop:
                       break

      async def task_handler(self, task_id, SE_task_link, done: bool=None):
            """
            Handles the process of viewing and performing a specific job task.

            Parameters:
            - SE_task_link (str): The URL of the job to be processed.
            - done (bool): Flag indicating whether the task has been marked as completed. Defaults to None
            """
            # Define necessary selectors for page verification
            selectors = [
               "select[id='select']", 'button:has-text("View Job")',
               'a[target="_blank"][style="text-decoration: none;"]'
            ]

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
               return await self.instance.blacklist(SE_task_link, banned=True)  # Blacklist the job URL

            # Extract the task URL from the page using the 3rd selector in the list
            telegram_link = await self.drive.extract_selector_link(selectors[2], self.page)

            try:
              # Execute the task worker with the task URL, job URL, and proof path
              done = await self.Join(telegram_link, SE_task_link, task_id)

            except Exception as error:
              # Log any exceptions that occur during task execution
              await self.drive.helper.print(f"[\033[93mSDE\033[0m]|\033[96mTelegram → view_task → task-workers\033[0m(\033[91merror\033[0m): {str(error)}")

            # Check if the task was successfully completed
            if done:
               # Submit the task using the stored task ID and media ID
               await self.drive.helper.schedule_tasks(task_id, self.media_id, 'Telegram', proof=True)

            else:
               # Authenticate the user
               if not await self.account_lookup():
                  # Halt automation due to invalid session
                  self.instance.sync_telegram = False

                  # Disable further Telegram processing until re-enabled externally
                  self.instance.telegram_disable = True

      async def Join(self, telegram_link, SE_task_link, task_id):
            """
            Joins a Telegram group or channel using an invite link.
            Handles both private and public invite formats.
            """
            # Define necessary selectors
            selectors = [
               'a[class="tgme_action_button_new tgme_action_web_button"]',
               'span[class="tgme_action_button_label"]:has-text("Open in Web")'
            ]

            # Selector for the Telegram group/channel title
            chat_selectors = [
               'div[class="ChatInfo"] div[class="info"]', 'button[class="btn-icon rp btn-menu-toggle"]',
               'div[class="HeaderActions"] button[aria-label="Search this chat"][title="Search this chat"]',
               'div[class="Transition"] div[class*="middle-column-footer"] div[class*="MessageSelectToolbar"]',
               'div[class="chat-info"] div[class="user-title"]', 'button[aria-label="More actions"][title="More actions"]',
               'div.ChatInfo div.info div.title.QljEeKI5 .fullName.AS54Cntu', 'div[class="ChatInfo"] div[class="info"] span[class="status"] span[class="group-status"]'
            ]

            # Verify page is accessible (check for poor internet connection)
            if not await self.drive.helper.site_lamba(telegram_link, self.page, silent=True):
               # Indicates network issue
               raise Exception('Internet issues!')

            # Ensure required UI elements are present
            if not await self.drive.await_selectors(selectors, self.page, silent=True):
               self.instance.sync_telegram = False

               # Raise an alert message indicating access is denied due to not being logged in
               raise Exception('\033[4m\033[91mAccess Denied!\033[0m please sign into your Teleram account to proceed')

            # Determine request type based on the link pattern
            if '/+' in telegram_link:
               # Handle invitation-style links (t.me/+xxxx → requires invite join)
               telethon_response = await self.invite_request(telegram_link, SE_task_link)
            else:
               # Handle standard channel/group links (t.me/xxxx → direct join)
               telethon_response = await self.channel_request(telegram_link, SE_task_link)

            # If request failed, stop and return False
            if telethon_response is False:
               return False

            # Extract the invitation URL
            invite_link  = await self.drive.extract_selector_link(selectors[0], self.page)

            # Navigate to the invite link
            if not await self.drive.helper.site_lamba(invite_link, self.page, timeout=20):
               # Indicates network issue
               return await self.drive.helper.print('[\033[93mSDE\033[0m]|\033[96mTelegram → workers → Join\033[0m(\033[91merror\033[0m): Poor Internet')

            # Define a lambda to check for each required chat-related selector
            async_check = lambda selector: self.drive.await_selectors(selector, self.page, timeout=30, silent=True)

            # Execute all selector checks concurrently
            results = await asyncio.gather(*[async_check(selector) for selector in chat_selectors])

            # Chcek if any of the selectors are found
            if not any(results):
               await self.drive.helper.print(f"[\033[93mALERT\033[0m]|\033[96mTelegram → workers → Join\033[0m(\033[91merror\033[0m): No required chat-related selector was detected")

            # Attempt to capture screenshot as proof
            if await self.drive.screen_shot(self.page, task_id):
               # Join successful
               return True

            await self.drive.helper.print(f"[\033[93mSDE\033[0m]|\033[96mTelegram → workers → Join\033[0m(\033[91merror\033[0m): screenshot capture failed")

      async def invite_request(self, telegram_link, SE_task_link):
            # Private invite link - extract hash
            invite_hash = telegram_link.split('+')[1]

            # Clean the username by removing any trailing non-alphabetic characters (e.g., query params or symbols)
            for char in invite_hash:
                if not char.isalpha() and not char.isdigit() and char not in ['_', '-']:
                   invite_hash = invite_hash.split(char)[0]
                   break

            # Attempt to join the private chat; ignore specific known exceptions
            try:
              await self.client(ImportChatInviteRequest(invite_hash))
            except Exception as error:
                   if not await self.telegram_errors(str(error), SE_task_link):
                      return False

      async def channel_request(self, telegram_link, SE_task_link):
            try:
              # Public invite link – extract the username from the URL by stripping trailing slash and splitting
              username = telegram_link.rstrip('/').split('/')[-1]

              # Ensure a valid username was extracted
              if not username:
                 raise Exception('Failed to extract a valid username from the invite link')

              # Clean the username by removing any trailing non-alphabetic characters (e.g., query params or symbols)
              for char in username:
                  if not char.isalpha() and not char.isdigit() and char not in ['_', '-']:
                     username = username.split(char)[0]

                     # Attempt to join the public channel by username
                     return await self.client(JoinChannelRequest(username))

            except Exception as error:
                   if not await self.telegram_errors(str(error), SE_task_link):
                      return False

      async def telegram_errors(self, error, SE_task_link):
            # List of messages that indicate a non-critical condition (handled gracefully)
            messages = [
              "You have successfully requested to join",
              "The authenticated user is already a participant of the chat",
              "The chat the user tried to join has expired and is not valid anymore"
            ]

            # Check if the error is NOT in known messages — treat it as unexpected and log it
            if not any([sms in error for sms in messages]):
               return await self.drive.helper.print(f"[\033[93mSDE\033[0m]|\033[96mTelegram → workers → invite_request\033[0m(\033[91merror\033[0m): {str(error)}")

            # If it's a known error and NOT about an expired link, it's acceptable — return True
            if messages[2] not in error:
               return True

            # If the error is due to an expired link, blacklist the associated task link
            await self.instance.blacklist(SE_task_link, banned=True)

            # Log the fact that the link was blacklisted due to expiration
            await self.drive.helper.print(f"[\033[93mSDE\033[0m]|\033[96mTelegram → workers\033[0m(\033[95merror\033[0m): Expired invite link detected — blacklisting URL")
