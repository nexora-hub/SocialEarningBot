import os
import requests



def analyze_file(name: str) -> str:
    # ─────────────────────────────────────────────
    # File Name Mapper
    # ─────────────────────────────────────────────

    if name == "storage_state.json":
       # Map file names depending on environment
       return name if ENVIRONMENT == "Local Machine" else "cloud_storage_state.json"
    return name


def detect_environment():
    # ─────────────────────────────────────────────
    # Environment Detection
    # ─────────────────────────────────────────────

    # Detect Fly.io → environment variables specific to Fly.io deployment
    if "FLY_APP_NAME" in os.environ or "FLY_ALLOC_ID" in os.environ:
        return "Fly.io VM"

    # Detect Render → environment variables unique to Render platform
    if "RENDER" in os.environ or "RENDER_SERVICE_ID" in os.environ:
        return "Render VM"

    # Detect Docker or Kubernetes → based on control group identifiers in /proc/1/cgroup
    try:
      with open("/proc/1/cgroup", "rt") as f:
           content = f.read()

           # Look for container-related keywords in the cgroup file
           if any(keyword in content for keyword in ["docker", "kubepods", "containerd"]):
              return "Container (Docker/Kubernetes)"
    except FileNotFoundError:
           # If /proc/1/cgroup does not exist (non-Linux systems), skip container detection
           pass

    # Detect CI/CD pipelines → many CI services set a generic "CI" environment variable
    if "CI" in os.environ:
        return "CI/CD Environment"

    # Default fallback → assume execution is on a local machine
    return "Local Machine"


def Upload(file_name: str) -> bool:
    # ─────────────────────────────────────────────
    # Upload Function
    # ─────────────────────────────────────────────

    # Prefix used for standardized error logging output
    error_prefix = "[\033[93mSDE\033[0m]|\033[96mOnline_storage → upload\033[0m(\033[91merror\033[0m): "

    try:
      # Open the file in binary read mode from the local storage directory
      with open("storage/" + file_name, "rb") as file:
           # Prepare the multipart/form-data payload with an analyzed filename
           payload = {"file": (analyze_file(file_name), file)}

           # Construct the full URL for uploading with authentication token
           url = f"{ONLINE_STORAGE}/upload/{ROOT_STORAGE}{DOWNLOAD_AUTH_TOKEN}"

           # Send POST request with the file payload
           response = requests.post(url, files=payload, timeout=15)

      # If upload is successful, return True to confirm completion
      if response.status_code == 200:
         return True

      # Otherwise, log the failure with status code and server response
      print (error_prefix + f"Server responded with {response.status_code} - {response.text}")

    # Handle connectivity-related issues (timeouts, DNS, etc.)
    except requests.RequestException:
           print (error_prefix + "Internet Error!")

    # Handle unexpected exceptions that may occur during upload
    except Exception as error:
           print (error_prefix + "{error}")

    # Return False if the upload fails at any point
    return False


def Download(file_name: str) -> bool:
    # ─────────────────────────────────────────────
    # Download Function
    # ─────────────────────────────────────────────

    # Prefix used for standardized error logging output
    error_prefix = "[\033[93mSDE\033[0m]|\033[96mOnline_storage → download\033[0m(\033[91merror\033[0m): "

    try:
      # Normalize / analyze filename before request
      mapped_name = analyze_file(file_name)

      # Request file from remote storage with timeout
      response = requests.get(f"{ONLINE_STORAGE}/download/{ROOT_STORAGE}/{mapped_name}{DOWNLOAD_AUTH_TOKEN}", timeout=15)

      # Save to local storage if download is successful
      if response.status_code == 200:
         with open("storage/" + file_name, "wb") as file:
              file.write(response.content)

         return True

      else:
         # Log server-side error response
         print (error_prefix + "Server responded with {response.status_code} - {response.text}")

    except requests.RequestException:
      # Handle networking / connectivity errors
      print (error_prefix + "Internet Error!")

    except Exception as error:
      # Catch unexpected runtime errors
      print (error_prefix + f"{error}")

    # Fallback: return False if anything failed
    return False


# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
ROOT_STORAGE = "socialearningbot"
ONLINE_STORAGE = "https://onlinestorage.onrender.com"
DOWNLOAD_AUTH_TOKEN = "?token=C4db07199f9d2C7"


# Cache the environment (avoid repeated checks)
ENVIRONMENT = detect_environment()
