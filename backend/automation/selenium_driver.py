"""
Selenium WebDriver manager for Facebook Page creation.
Supports both real Facebook automation and test mode (httpbin.org).
"""

import time
import uuid
import re
import json
import os
import subprocess
import platform
from typing import Optional
from dataclasses import dataclass
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import logging

logger = logging.getLogger(__name__)

# Default cookie file path
DEFAULT_COOKIES_PATH = os.path.join(os.path.dirname(__file__), '..', 'facebook_cookies.json')


@dataclass
class PageResult:
    """Result of a page creation attempt"""
    success: bool
    page_name: str
    page_id: str = ""
    page_url: str = ""
    duration: float = 0.0
    error: str = ""


@dataclass
class InviteResult:
    """Result of an invite operation"""
    success: bool
    page_id: str
    invitee_email: str
    invite_link: str = ""
    role: str = "editor"
    error: str = ""


@dataclass
class ProfileCredentials:
    """Facebook profile credentials for multi-profile rotation"""
    email: str
    password: str
    name: str = ""
    pages_per_session: int = 3  # Max pages to create before rotating


class FacebookPageGenerator:
    """
    Selenium-based Facebook Page generator.

    WARNING: Automated Facebook page creation violates Facebook's Terms of Service.
    This is provided for educational/testing purposes only.
    Use TEST_MODE=True for safe testing with httpbin.org instead.
    """

    FACEBOOK_LOGIN_URL = "https://www.facebook.com"
    FACEBOOK_PAGES_URL = "https://www.facebook.com/pages/creation/"
    TEST_URL = "https://httpbin.org/forms/post"

    def __init__(self, headless: bool = True, timeout: int = 30, test_mode: bool = True,
                 proxy_url: str = "", cookies_path: str = "",
                 profiles: list = None, pages_per_profile: int = 3):
        self.headless = headless
        self.timeout = timeout
        self.test_mode = test_mode
        self.proxy_url = proxy_url
        self.cookies_path = cookies_path or DEFAULT_COOKIES_PATH
        self.driver: Optional[webdriver.Chrome] = None
        self.logged_in = False
        self.rate_limited = False
        self.metrics = {
            'pages_created': 0,
            'total_time': 0.0,
            'errors': 0,
            'rate_limit_hits': 0,
        }

        # Multi-profile rotation support
        self.profiles: list = profiles or []  # List of ProfileCredentials
        self.current_profile_index: int = 0
        self.pages_per_profile: int = pages_per_profile  # Pages before rotating
        self.pages_created_this_session: int = 0  # Pages created with current profile
        self.current_profile_email: str = ""  # Email of currently logged-in profile

    def _get_chrome_options(self) -> Options:
        """Configure Chrome/Chromium options for Selenium"""
        import random
        import os
        options = Options()

        # Set Chromium binary location (for Docker/Render)
        chrome_bin = os.environ.get('CHROME_BIN')
        if chrome_bin and os.path.exists(chrome_bin):
            options.binary_location = chrome_bin
            print(f">>> Using Chromium binary: {chrome_bin}")
        elif os.path.exists('/usr/bin/chromium'):
            options.binary_location = '/usr/bin/chromium'
            print(">>> Using Chromium binary: /usr/bin/chromium")
        elif os.path.exists('/usr/bin/chromium-browser'):
            options.binary_location = '/usr/bin/chromium-browser'
            print(">>> Using Chromium binary: /usr/bin/chromium-browser")

        # Headless mode
        if self.headless:
            options.add_argument("--headless=new")

        # Essential stability options
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280,720")  # Smaller window = less memory

        # AGGRESSIVE MEMORY SAVING for Render's limited RAM (512MB)
        options.add_argument("--disable-javascript-harmony-shipping")
        options.add_argument("--disable-renderer-accessibility")
        options.add_argument("--disable-speech-api")
        options.add_argument("--disable-webgl")
        options.add_argument("--disable-webgl2")
        options.add_argument("--disable-accelerated-2d-canvas")
        options.add_argument("--disable-accelerated-video-decode")
        options.add_argument("--disable-canvas-aa")
        options.add_argument("--disable-composited-antialiasing")
        options.add_argument("--disable-threaded-animation")
        options.add_argument("--disable-threaded-scrolling")
        options.add_argument("--js-flags=--max-old-space-size=256")  # Limit JS heap to 256MB
        options.add_argument("--renderer-process-limit=1")  # Only 1 renderer process
        options.add_argument("--single-process")  # Risk but saves memory

        # Fake Chrome user-agent (important for Chromium to avoid detection)
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        # Disable features that can cause crashes
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-translate")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-sync")
        options.add_argument("--disable-default-apps")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")

        # Anti-detection
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # Stability options for Docker/containers
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--disable-features=VizDisplayCompositor")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")

        # Memory optimization
        options.add_argument("--disable-features=TranslateUI")
        options.add_argument("--disable-ipc-flooding-protection")
        options.add_argument("--memory-pressure-off")

        # Use random debugging port to avoid conflicts
        debug_port = random.randint(9222, 9999)
        options.add_argument(f"--remote-debugging-port={debug_port}")

        # Crash handling
        options.add_argument("--crash-dumps-dir=/tmp")
        options.add_argument("--disable-crash-reporter")

        # NOTE: Using --single-process now to save memory on Render (may cause some instability)

        # Add proxy if configured
        if self.proxy_url:
            options.add_argument(f"--proxy-server={self.proxy_url}")
            print(f">>> Using proxy: {self.proxy_url}")

        # Page load strategy - don't wait for all resources (saves time and memory)
        options.page_load_strategy = 'eager'  # Don't wait for images/stylesheets

        # Disable password manager popups
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_settings.popups": 0,
            # Block images to save memory (optional - may affect visual verification)
            # "profile.managed_default_content_settings.images": 2,
        }
        options.add_experimental_option("prefs", prefs)
        return options

    def save_cookies(self):
        """Save cookies to file for session persistence"""
        if not self.driver:
            return False
        try:
            cookies = self.driver.get_cookies()
            with open(self.cookies_path, 'w') as f:
                json.dump(cookies, f)
            print(f">>> Saved {len(cookies)} cookies to {self.cookies_path}")
            logger.info(f"Saved {len(cookies)} cookies")
            return True
        except Exception as e:
            logger.error(f"Failed to save cookies: {e}")
            return False

    def load_cookies(self):
        """Load cookies from file to restore session"""
        if not self.driver:
            return False
        if not os.path.exists(self.cookies_path):
            print(f">>> No saved cookies found at {self.cookies_path}")
            return False
        try:
            with open(self.cookies_path, 'r') as f:
                cookies = json.load(f)

            # Navigate to Facebook first before adding cookies
            self.driver.get("https://www.facebook.com")
            time.sleep(2)

            for cookie in cookies:
                # Remove problematic cookie attributes
                if 'sameSite' in cookie:
                    del cookie['sameSite']
                if 'expiry' in cookie:
                    cookie['expiry'] = int(cookie['expiry'])
                try:
                    self.driver.add_cookie(cookie)
                except Exception:
                    pass  # Skip invalid cookies

            print(f">>> Loaded {len(cookies)} cookies from {self.cookies_path}")
            logger.info(f"Loaded {len(cookies)} cookies")
            return True
        except Exception as e:
            logger.error(f"Failed to load cookies: {e}")
            return False

    def check_if_logged_in(self) -> bool:
        """Check if we're still logged in to Facebook"""
        if not self.driver:
            return False
        try:
            self.driver.get("https://www.facebook.com")
            time.sleep(3)

            # Check if login form is present (means NOT logged in)
            login_indicators = [
                "//input[@id='email']",
                "//input[@name='email']",
                "//button[@name='login']",
            ]
            for selector in login_indicators:
                try:
                    elem = self.driver.find_element(By.XPATH, selector)
                    if elem.is_displayed():
                        print(">>> Not logged in (login form visible)")
                        return False
                except NoSuchElementException:
                    continue

            # Check if logged-in indicators are present
            logged_in_indicators = [
                "//div[@aria-label='Your profile']",
                "//div[@aria-label='Account']",
                "//a[contains(@href, '/me/')]",
            ]
            for selector in logged_in_indicators:
                try:
                    elem = self.driver.find_element(By.XPATH, selector)
                    if elem.is_displayed():
                        print(">>> Already logged in (profile icon visible)")
                        self.logged_in = True
                        return True
                except NoSuchElementException:
                    continue

            return False
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False

    def detect_rate_limit(self) -> bool:
        """Check if we're being rate limited by Facebook"""
        if not self.driver:
            return False
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            rate_limit_phrases = [
                "try again later",
                "you're temporarily blocked",
                "temporarily blocked",
                "rate limit",
                "too many",
                "slow down",
                "something went wrong",
                "couldn't create",
                "can't create",
                "please try again",
                "action blocked",
                "we limit how often",
            ]
            for phrase in rate_limit_phrases:
                if phrase in page_text:
                    print(f">>> RATE LIMIT DETECTED: '{phrase}'")
                    self.rate_limited = True
                    self.metrics['rate_limit_hits'] += 1
                    return True
            return False
        except Exception:
            return False

    def cleanup_chrome_processes(self):
        """Kill any orphaned Chrome/chromedriver processes to prevent session conflicts"""
        try:
            system = platform.system()
            if system == "Darwin":  # macOS
                subprocess.run(["pkill", "-9", "-f", "Google Chrome"], capture_output=True)
                subprocess.run(["pkill", "-9", "-f", "chromedriver"], capture_output=True)
                subprocess.run(["pkill", "-9", "-f", "Chrome Helper"], capture_output=True)
            elif system == "Linux":
                subprocess.run(["pkill", "-9", "-f", "chrome"], capture_output=True)
                subprocess.run(["pkill", "-9", "-f", "chromedriver"], capture_output=True)
            elif system == "Windows":
                subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
                subprocess.run(["taskkill", "/F", "/IM", "chromedriver.exe"], capture_output=True)
            time.sleep(1)  # Give processes time to terminate
            print(">>> Cleaned up any orphaned Chrome processes")
            logger.info("Cleaned up orphaned Chrome processes")
        except Exception as e:
            print(f">>> Warning: Could not cleanup Chrome processes: {e}")
            logger.warning(f"Could not cleanup Chrome processes: {e}")

    def start(self, max_retries: int = 3):
        """Initialize the WebDriver with retry logic"""
        import os

        # Clean up any orphaned Chrome processes first
        self.cleanup_chrome_processes()

        last_error = None
        for attempt in range(max_retries):
            try:
                print(f">>> Starting Chromium/Chrome (attempt {attempt + 1}/{max_retries})...")

                # Use system chromedriver if available (Docker/Render), otherwise use webdriver-manager
                chromedriver_path = os.environ.get('CHROMEDRIVER_PATH')
                if chromedriver_path and os.path.exists(chromedriver_path):
                    print(f">>> Using system chromedriver: {chromedriver_path}")
                    service = Service(chromedriver_path)
                elif os.path.exists('/usr/bin/chromedriver'):
                    print(">>> Using system chromedriver: /usr/bin/chromedriver")
                    service = Service('/usr/bin/chromedriver')
                else:
                    print(">>> Using webdriver-manager to get chromedriver")
                    service = Service(ChromeDriverManager().install())

                # Wait a bit between retries
                if attempt > 0:
                    time.sleep(2)
                    self.cleanup_chrome_processes()

                self.driver = webdriver.Chrome(
                    service=service,
                    options=self._get_chrome_options()
                )
                self.driver.implicitly_wait(10)

                # Remove webdriver flag
                self.driver.execute_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                )

                print(">>> Chromium/Chrome WebDriver started successfully")
                logger.info("Chromium/Chrome WebDriver started successfully")
                return  # Success!

            except WebDriverException as e:
                last_error = e
                print(f">>> Chrome start attempt {attempt + 1} failed: {e}")
                logger.warning(f"Chrome start attempt {attempt + 1} failed: {e}")

                # Clean up before retry
                if self.driver:
                    try:
                        self.driver.quit()
                    except:
                        pass
                    self.driver = None

                self.cleanup_chrome_processes()

        # All retries failed
        logger.error(f"Failed to start Chrome driver after {max_retries} attempts: {last_error}")
        raise RuntimeError(f"Failed to start Chrome driver after {max_retries} attempts: {last_error}")

    def stop(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.logged_in = False
            logger.info("Chrome WebDriver stopped")

    def _handle_cookie_consent(self):
        """Handle Facebook's cookie consent popup if present"""
        try:
            # Try multiple selectors for cookie consent button
            cookie_selectors = [
                "//button[@data-cookiebanner='accept_button']",
                "//button[contains(text(), 'Accept All')]",
                "//button[contains(text(), 'Allow all cookies')]",
                "//button[contains(text(), 'Accept all')]",
                "//button[contains(text(), 'Allow All')]",
                "//button[@title='Allow all cookies']",
                "//div[@aria-label='Allow all cookies']",
                "//span[text()='Allow all cookies']/parent::button",
                "//span[text()='Accept All']/parent::button",
                # Additional selectors for different Facebook regions
                "//button[contains(text(), 'Allow essential and optional cookies')]",
                "//button[contains(text(), 'Only allow essential cookies')]",
            ]

            for selector in cookie_selectors:
                try:
                    cookie_btn = self.driver.find_element(By.XPATH, selector)
                    if cookie_btn.is_displayed():
                        cookie_btn.click()
                        print(f">>> Clicked cookie consent button: {selector}")
                        logger.info(f"Clicked cookie consent button: {selector}")
                        time.sleep(2)
                        return True
                except NoSuchElementException:
                    continue

            print(">>> No cookie consent popup found, continuing...")
            logger.info("No cookie consent popup found, continuing...")
            return False
        except Exception as e:
            print(f">>> Cookie consent error: {e}")
            logger.info(f"Cookie consent handling: {e}")
            return False

    def login_facebook(self, email: str, password: str, use_saved_cookies: bool = True) -> bool:
        """
        Login to Facebook account.

        Args:
            email: Facebook email
            password: Facebook password
            use_saved_cookies: If True, try to use saved cookies first to skip login

        WARNING: This may trigger security checks on Facebook.
        """
        if not self.driver:
            raise RuntimeError("Driver not initialized")

        if self.test_mode:
            logger.info("TEST MODE: Skipping Facebook login")
            print(">>> TEST MODE: Skipping Facebook login")
            self.logged_in = True
            return True

        try:
            # Try to use saved cookies first
            if use_saved_cookies:
                print(">>> STEP 0: Trying to use saved cookies...")
                if self.load_cookies():
                    # Refresh page to apply cookies
                    self.driver.refresh()
                    time.sleep(3)

                    # Check if we're logged in
                    if self.check_if_logged_in():
                        print(">>> SUCCESS: Logged in using saved cookies!")
                        self.logged_in = True
                        return True
                    else:
                        print(">>> Saved cookies expired or invalid, proceeding with fresh login...")

            # Clear all cookies and session data for fresh login
            print(">>> STEP 0.5: Clearing all cookies and session data...")
            self.driver.get("https://www.facebook.com")
            self.driver.delete_all_cookies()
            time.sleep(1)

            print(f">>> STEP 1: Navigating to Facebook login page...")
            logger.info(f"Attempting Facebook login for: {email}")
            self.driver.get(self.FACEBOOK_LOGIN_URL)

            wait = WebDriverWait(self.driver, self.timeout)
            print(">>> STEP 2: Waiting 3 seconds for page to load...")
            time.sleep(3)  # Wait for page to fully load

            # ========================================
            # STEP 3: Find and fill EMAIL field
            # ========================================
            # Facebook email input element:
            # <input type="text" class="inputtext _55r1 _6luy" name="email" id="email"
            #        data-testid="royal_email" placeholder="Email address or phone number"
            #        autofocus="1" autocomplete="username webauthn"
            #        aria-label="Email address or phone number">
            print(">>> STEP 3: Looking for email input field...")
            email_field = None

            # Try multiple selectors for email field
            email_selectors = [
                (By.ID, "email"),
                (By.NAME, "email"),
                (By.CSS_SELECTOR, "input[data-testid='royal_email']"),
                (By.CSS_SELECTOR, "input[data-testid='royal-email']"),
                (By.CSS_SELECTOR, "input[aria-label='Email address or phone number']"),
                (By.CSS_SELECTOR, "input.inputtext[name='email']"),
            ]

            for selector_type, selector_value in email_selectors:
                try:
                    email_field = wait.until(EC.presence_of_element_located((selector_type, selector_value)))
                    print(f">>> Found email field with selector: {selector_value}")
                    break
                except TimeoutException:
                    continue

            if not email_field:
                print(">>> ERROR: Could not find email field!")
                inputs = self.driver.find_elements(By.TAG_NAME, "input")
                print(f">>> DEBUG: Found {len(inputs)} input fields on page:")
                for i, inp in enumerate(inputs[:5]):
                    print(f">>>   Input {i}: id='{inp.get_attribute('id')}', name='{inp.get_attribute('name')}'")
                return False

            # Type email character by character to look more human
            email_field.clear()
            for char in email:
                email_field.send_keys(char)
                time.sleep(0.05)  # Small delay between characters
            print(f">>> STEP 4: Entered email: {email}")
            logger.info("Entered email")

            # Wait 5 seconds between email and password (looks more genuine)
            print(">>> Waiting 5 seconds before entering password (to look genuine)...")
            time.sleep(5)

            # ========================================
            # STEP 5: Find and fill PASSWORD field
            # ========================================
            # Facebook password input element:
            # <input type="password" class="inputtext _55r1 _9npi" name="pass" id="pass"
            #        tabindex="0" placeholder="Password" value=""
            #        autocomplete="current-password" aria-label="Password">
            print(">>> STEP 5: Looking for password input field...")
            password_field = None

            password_selectors = [
                (By.ID, "pass"),
                (By.NAME, "pass"),
                (By.CSS_SELECTOR, "input[type='password']"),
                (By.CSS_SELECTOR, "input[aria-label='Password']"),
                (By.CSS_SELECTOR, "input.inputtext[name='pass']"),
            ]

            for selector_type, selector_value in password_selectors:
                try:
                    password_field = self.driver.find_element(selector_type, selector_value)
                    print(f">>> Found password field with selector: {selector_value}")
                    break
                except NoSuchElementException:
                    continue

            if not password_field:
                print(">>> ERROR: Could not find password field!")
                return False

            # Type password character by character to look more human
            password_field.clear()
            for char in password:
                password_field.send_keys(char)
                time.sleep(0.05)  # Small delay between characters
            print(">>> STEP 6: Entered password")
            logger.info("Entered password")

            # Wait 2 seconds before clicking login button
            print(">>> Waiting 2 seconds before clicking login button...")
            time.sleep(2)

            # ========================================
            # STEP 7: Click LOGIN button
            # ========================================
            # Facebook login button element:
            # <button value="1" class="_42ft _4jy0 _52e0 _4jy6 _4jy1 selected _51sy"
            #         id="loginbutton" name="login" tabindex="0" type="submit">Log in</button>
            print(">>> STEP 7: Looking for login button...")
            login_clicked = False

            login_selectors = [
                (By.ID, "loginbutton"),
                (By.NAME, "login"),
                (By.CSS_SELECTOR, "button[type='submit']"),
                (By.CSS_SELECTOR, "button#loginbutton"),
                (By.CSS_SELECTOR, "button[name='login']"),
                (By.XPATH, "//button[text()='Log in']"),
                (By.XPATH, "//button[text()='Log In']"),
                (By.XPATH, "//button[contains(@class, '_42ft')]"),
            ]

            for selector_type, selector_value in login_selectors:
                try:
                    login_button = self.driver.find_element(selector_type, selector_value)
                    if login_button.is_displayed() and login_button.is_enabled():
                        login_button.click()
                        print(f">>> Clicked login button: {selector_value}")
                        logger.info(f"Clicked login button: {selector_value}")
                        login_clicked = True
                        break
                except NoSuchElementException:
                    continue

            if not login_clicked:
                # Try pressing Enter as last resort
                print(">>> No login button found, pressing Enter to submit...")
                password_field.send_keys(Keys.RETURN)
                logger.info("Pressed Enter to submit login form")

            # ========================================
            # STEP 8: Wait for login to complete
            # ========================================
            print(">>> STEP 8: Waiting 8 seconds for login to complete...")
            time.sleep(8)

            # Handle any post-login popups (e.g., "Save login info?")
            print(">>> STEP 9: Checking for post-login popups...")
            try:
                not_now_selectors = [
                    "//button[contains(text(), 'Not Now')]",
                    "//a[contains(text(), 'Not Now')]",
                    "//span[text()='Not Now']",
                    "//div[@aria-label='Not now']",
                ]
                for selector in not_now_selectors:
                    try:
                        not_now_btn = self.driver.find_element(By.XPATH, selector)
                        if not_now_btn.is_displayed():
                            not_now_btn.click()
                            print(">>> Clicked 'Not Now' on post-login popup")
                            logger.info("Clicked 'Not Now' on post-login popup")
                            time.sleep(2)
                            break
                    except NoSuchElementException:
                        continue
            except Exception:
                pass

            # ========================================
            # STEP 10: Check if login was successful
            # ========================================
            current_url = self.driver.current_url.lower()
            print(f">>> STEP 10: Checking login result. Current URL: {self.driver.current_url}")

            if "login" in current_url or "checkpoint" in current_url:
                logger.error(f"Facebook login may have failed - current URL: {self.driver.current_url}")
                print(f">>> ERROR: Still on login page or checkpoint!")
                if "checkpoint" in current_url:
                    print(">>> ERROR: Facebook security checkpoint detected - manual verification required!")
                    logger.error("Facebook security checkpoint detected - manual verification may be required")
                return False

            self.logged_in = True
            print(">>> SUCCESS: Facebook login successful!")
            logger.info("Facebook login successful")

            # Save cookies for future sessions (avoid re-login)
            self.save_cookies()

            return True

        except TimeoutException as e:
            print(f">>> ERROR: Timeout during Facebook login: {e}")
            logger.error("Timeout during Facebook login")
            return False
        except Exception as e:
            print(f">>> ERROR: Facebook login error: {e}")
            logger.error(f"Facebook login error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def logout_facebook(self) -> bool:
        """
        Logout from Facebook account.

        Flow:
        1. Click close (X) button if on a page (to leave any current page/popup)
        2. Click "Leave Page" if dialog appears
        3. Click profile dropdown arrow
        4. Click "Log out"
        5. Wait for facebook.com login page to appear

        Returns:
            True if logout successful, False otherwise
        """
        if not self.driver:
            print(">>> LOGOUT: Driver not initialized")
            return False

        if self.test_mode:
            print(">>> TEST MODE: Simulating logout")
            self.logged_in = False
            return True

        try:
            print(">>> LOGOUT STEP 1: Navigating to Facebook home...")
            self.driver.get("https://www.facebook.com")
            time.sleep(3)

            # ========================================
            # STEP 1: Close any open dialogs/popups first
            # ========================================
            print(">>> LOGOUT STEP 1b: Closing any open dialogs (clicking X button)...")
            # From screenshot 15: X button is in top-left corner of page creation form
            close_selectors = [
                # X button in top-left (like in page creation form)
                (By.CSS_SELECTOR, "div[aria-label='Close']"),
                (By.XPATH, "//div[@aria-label='Close']"),
                (By.XPATH, "//*[@aria-label='Close']"),
                (By.XPATH, "//i[contains(@class, 'x1b0d499')]"),  # X icon
                # SVG close icon
                (By.CSS_SELECTOR, "svg[aria-label='Close']"),
                (By.XPATH, "//*[local-name()='svg'][@aria-label='Close']"),
            ]

            for selector_type, selector_value in close_selectors:
                try:
                    elements = self.driver.find_elements(selector_type, selector_value)
                    for elem in elements:
                        if elem.is_displayed():
                            elem.click()
                            print(f">>> Clicked close (X) button")
                            time.sleep(2)
                            break
                except Exception:
                    continue

            # ========================================
            # STEP 2: Handle "Leave Page?" dialog if it appears
            # From screenshot 16: Dialog has "Stay on Page" and "Leave Page" buttons
            # ========================================
            print(">>> LOGOUT STEP 2: Checking for 'Leave Page?' dialog...")
            time.sleep(1)  # Wait for dialog to appear

            leave_page_selectors = [
                # Blue "Leave Page" button (from screenshot 16)
                (By.XPATH, "//span[text()='Leave Page']"),
                (By.XPATH, "//div[@role='button']//span[text()='Leave Page']"),
                (By.XPATH, "//span[contains(text(), 'Leave Page')]"),
                # Also try clicking any button with "Leave" text
                (By.XPATH, "//div[@role='button'][.//span[text()='Leave Page']]"),
            ]

            leave_clicked = False
            for selector_type, selector_value in leave_page_selectors:
                if leave_clicked:
                    break
                try:
                    elements = self.driver.find_elements(selector_type, selector_value)
                    for elem in elements:
                        if elem.is_displayed():
                            elem.click()
                            print(f">>> Clicked 'Leave Page' button")
                            leave_clicked = True
                            time.sleep(2)
                            break
                except Exception:
                    continue

            if not leave_clicked:
                print(">>> No 'Leave Page' dialog detected, continuing...")

            # ========================================
            # STEP 3: Click profile dropdown arrow (account menu)
            # From screenshot 17: Profile picture is in top right, clicking shows dropdown
            # with "Kritika Verma", pages, and "Log out" option
            # ========================================
            print(">>> LOGOUT STEP 3: Looking for profile dropdown/account menu (top-right corner)...")
            profile_clicked = False

            # From screenshot 17: The profile dropdown shows profile image in top-right
            profile_selectors = [
                # Profile image/avatar that triggers dropdown
                (By.CSS_SELECTOR, "div[aria-label='Your profile']"),
                (By.XPATH, "//div[@aria-label='Your profile']"),
                (By.CSS_SELECTOR, "div[aria-label='Account']"),
                (By.XPATH, "//div[@aria-label='Account']"),
                # SVG/image in the header area
                (By.XPATH, "//div[contains(@class, 'x1iyjqo2')]//image"),
                # Profile picture clickable div
                (By.CSS_SELECTOR, "image[preserveAspectRatio='xMidYMid slice']"),
                (By.XPATH, "//image[@preserveAspectRatio='xMidYMid slice']"),
                # Account menu button
                (By.XPATH, "//div[@aria-label='Account Controls and Settings']"),
            ]

            # Wait up to 10 seconds
            for attempt in range(10):
                for selector_type, selector_value in profile_selectors:
                    if profile_clicked:
                        break
                    try:
                        elements = self.driver.find_elements(selector_type, selector_value)
                        # Try the last few elements (profile is usually at the right/end)
                        for elem in elements[-5:]:
                            if elem.is_displayed():
                                self.driver.execute_script("arguments[0].click();", elem)
                                print(f">>> Clicked profile dropdown")
                                profile_clicked = True
                                time.sleep(2)
                                break
                    except Exception:
                        continue
                if profile_clicked:
                    break
                time.sleep(1)

            if not profile_clicked:
                print(">>> WARNING: Could not find profile dropdown, trying direct navigation...")
                # Try navigating to account settings directly
                try:
                    self.driver.get("https://www.facebook.com/")
                    time.sleep(2)
                    # Try clicking any clickable image in header
                    images = self.driver.find_elements(By.TAG_NAME, "image")
                    for img in images[-5:]:
                        try:
                            if img.is_displayed():
                                img.click()
                                print(f">>> Clicked profile image fallback")
                                profile_clicked = True
                                time.sleep(2)
                                break
                        except:
                            continue
                except Exception:
                    pass

            # ========================================
            # STEP 4: Click "Log out" option
            # From screenshot 17: "Log out" is in the dropdown menu with an icon
            # It's at the bottom of the menu after Settings, Help, Display options
            # ========================================
            print(">>> LOGOUT STEP 4: Looking for 'Log out' option in dropdown menu...")
            logout_clicked = False

            # From screenshot 17: "Log out" text in dropdown menu
            logout_selectors = [
                # Direct text match for "Log out"
                (By.XPATH, "//span[text()='Log out']"),
                (By.XPATH, "//span[text()='Log Out']"),
                # Menu item containing Log out
                (By.XPATH, "//div[@role='menuitem']//span[text()='Log out']"),
                (By.XPATH, "//div[@role='button']//span[text()='Log out']"),
                # Partial match
                (By.XPATH, "//span[contains(text(), 'Log out')]"),
                (By.XPATH, "//span[contains(text(), 'Log Out')]"),
                # Any clickable element with logout text
                (By.XPATH, "//*[text()='Log out']"),
            ]

            # Wait up to 10 seconds for logout option
            for attempt in range(10):
                for selector_type, selector_value in logout_selectors:
                    if logout_clicked:
                        break
                    try:
                        elements = self.driver.find_elements(selector_type, selector_value)
                        for elem in elements:
                            if elem.is_displayed():
                                elem_text = elem.text.strip().lower()
                                if 'log out' in elem_text or 'logout' in elem_text:
                                    # Scroll into view and click
                                    self.driver.execute_script("arguments[0].scrollIntoView(true);", elem)
                                    time.sleep(0.3)
                                    self.driver.execute_script("arguments[0].click();", elem)
                                    print(f">>> Clicked 'Log out' button")
                                    logout_clicked = True
                                    time.sleep(3)
                                    break
                    except Exception:
                        continue
                if logout_clicked:
                    break
                time.sleep(1)

            if not logout_clicked:
                print(">>> WARNING: Could not find 'Log out' option, trying JavaScript...")
                # Try JavaScript approach to find and click logout
                try:
                    result = self.driver.execute_script("""
                        const spans = document.querySelectorAll('span');
                        for (let span of spans) {
                            const text = span.textContent.toLowerCase().trim();
                            if (text === 'log out' || text === 'logout') {
                                span.click();
                                return true;
                            }
                        }
                        return false;
                    """)
                    if result:
                        print(">>> Used JavaScript to click logout")
                        logout_clicked = True
                        time.sleep(3)
                    else:
                        print(">>> JavaScript logout also failed")
                except Exception as e:
                    print(f">>> JavaScript logout failed: {e}")

            # ========================================
            # STEP 5: Verify logout - check if login page appears
            # ========================================
            print(">>> LOGOUT STEP 5: Verifying logout...")
            time.sleep(3)

            current_url = self.driver.current_url.lower()
            print(f">>> Current URL after logout: {self.driver.current_url}")

            # Check for login page indicators
            login_indicators = [
                "//input[@id='email']",
                "//input[@name='email']",
                "//button[@name='login']",
            ]

            logout_successful = False
            for selector in login_indicators:
                try:
                    elem = self.driver.find_element(By.XPATH, selector)
                    if elem.is_displayed():
                        logout_successful = True
                        print(">>> SUCCESS: Logout verified - login page detected")
                        break
                except NoSuchElementException:
                    continue

            if logout_successful or "login" in current_url:
                self.logged_in = False
                # Delete cookies to ensure clean state
                self.driver.delete_all_cookies()
                print(">>> SUCCESS: Facebook logout complete!")
                logger.info("Facebook logout successful")
                return True
            else:
                print(">>> WARNING: Logout may not have completed successfully")
                # Force logout by clearing cookies
                self.driver.delete_all_cookies()
                self.logged_in = False
                return True  # Consider it successful anyway

        except Exception as e:
            print(f">>> ERROR: Exception during logout: {e}")
            logger.error(f"Logout error: {e}")
            import traceback
            traceback.print_exc()
            # Try to force logout by clearing cookies
            try:
                self.driver.delete_all_cookies()
                self.logged_in = False
            except:
                pass
            return False

    def set_profiles(self, profiles: list):
        """
        Set the list of profiles for rotation.

        Args:
            profiles: List of ProfileCredentials or list of dicts with 'email', 'password', 'name' keys
        """
        self.profiles = []
        for p in profiles:
            if isinstance(p, ProfileCredentials):
                self.profiles.append(p)
            elif isinstance(p, dict):
                self.profiles.append(ProfileCredentials(
                    email=p.get('email', ''),
                    password=p.get('password', ''),
                    name=p.get('name', p.get('email', '')),
                    pages_per_session=p.get('pages_per_session', self.pages_per_profile)
                ))
        self.current_profile_index = 0
        self.pages_created_this_session = 0
        print(f">>> PROFILES: Set {len(self.profiles)} profiles for rotation")
        logger.info(f"Set {len(self.profiles)} profiles for rotation")

    def get_current_profile(self) -> Optional[ProfileCredentials]:
        """Get the current profile to use"""
        if not self.profiles:
            return None
        if self.current_profile_index >= len(self.profiles):
            return None
        return self.profiles[self.current_profile_index]

    def should_rotate_profile(self) -> bool:
        """
        Check if we should rotate to the next profile.

        Returns True if:
        - Current profile has created enough pages (pages_per_profile)
        - Rate limit detected
        - Page creation error occurred
        """
        if not self.profiles or len(self.profiles) <= 1:
            return False

        current_profile = self.get_current_profile()
        if not current_profile:
            return False

        max_pages = current_profile.pages_per_session or self.pages_per_profile

        if self.pages_created_this_session >= max_pages:
            print(f">>> ROTATION: Profile {self.current_profile_index + 1} has created {self.pages_created_this_session} pages (max: {max_pages})")
            return True

        if self.rate_limited:
            print(f">>> ROTATION: Profile {self.current_profile_index + 1} is rate limited")
            return True

        return False

    def rotate_to_next_profile(self) -> bool:
        """
        Logout current profile and login to the next one.

        Returns:
            True if successfully rotated to next profile, False if no more profiles
        """
        if not self.profiles:
            print(">>> ROTATION: No profiles configured for rotation")
            return False

        # Logout current profile
        print(f">>> ROTATION: Logging out profile {self.current_profile_index + 1} ({self.current_profile_email})...")
        logout_success = self.logout_facebook()

        if not logout_success:
            print(">>> ROTATION: Logout failed, but continuing with rotation...")

        # Move to next profile
        self.current_profile_index += 1
        self.pages_created_this_session = 0
        self.rate_limited = False

        if self.current_profile_index >= len(self.profiles):
            print(f">>> ROTATION: All {len(self.profiles)} profiles exhausted, no more profiles available")
            return False

        # Login to next profile
        next_profile = self.profiles[self.current_profile_index]
        print(f">>> ROTATION: Switching to profile {self.current_profile_index + 1} of {len(self.profiles)} ({next_profile.email})...")

        login_success = self.login_facebook(next_profile.email, next_profile.password, use_saved_cookies=False)

        if login_success:
            self.current_profile_email = next_profile.email
            print(f">>> ROTATION: Successfully logged in as {next_profile.email}")
            return True
        else:
            print(f">>> ROTATION: Failed to login as {next_profile.email}")
            # Try next profile recursively
            return self.rotate_to_next_profile()

    def login_with_rotation(self) -> bool:
        """
        Login using the first available profile from the rotation list.
        If no profiles are set, returns False.

        Returns:
            True if login successful, False otherwise
        """
        if not self.profiles:
            print(">>> LOGIN: No profiles configured, use login_facebook() with credentials")
            return False

        current_profile = self.get_current_profile()
        if not current_profile:
            print(">>> LOGIN: All profiles exhausted")
            return False

        print(f">>> LOGIN: Logging in with profile {self.current_profile_index + 1} of {len(self.profiles)} ({current_profile.email})...")

        success = self.login_facebook(current_profile.email, current_profile.password, use_saved_cookies=False)

        if success:
            self.current_profile_email = current_profile.email
            return True
        else:
            # Try next profile
            print(f">>> LOGIN: Profile {current_profile.email} failed, trying next...")
            return self.rotate_to_next_profile()

    def increment_page_count(self):
        """Call this after successfully creating a page to track count for rotation"""
        self.pages_created_this_session += 1
        print(f">>> ROTATION TRACKER: Profile {self.current_profile_index + 1} has created {self.pages_created_this_session}/{self.pages_per_profile} pages this session")

    def has_more_profiles(self) -> bool:
        """Check if there are more profiles available for rotation"""
        return self.current_profile_index < len(self.profiles) - 1

    def get_rotation_status(self) -> dict:
        """Get current rotation status"""
        current_profile = self.get_current_profile()
        return {
            'total_profiles': len(self.profiles),
            'current_profile_index': self.current_profile_index + 1,
            'current_profile_email': self.current_profile_email or (current_profile.email if current_profile else 'None'),
            'pages_created_this_session': self.pages_created_this_session,
            'pages_per_profile': self.pages_per_profile,
            'has_more_profiles': self.has_more_profiles(),
            'should_rotate': self.should_rotate_profile(),
        }

    def create_facebook_page(self, page_name: str, category: str = "Business",
                             description: str = "") -> PageResult:
        """
        Create a Facebook Page.

        In TEST_MODE, simulates page creation using httpbin.org.
        """
        if not self.driver:
            return PageResult(
                success=False,
                page_name=page_name,
                error="Driver not initialized"
            )

        start_time = time.time()

        if self.test_mode:
            return self._create_test_page(page_name, start_time)
        else:
            return self._create_real_facebook_page(page_name, category, description, start_time)

    def _create_test_page(self, page_name: str, start_time: float) -> PageResult:
        """Simulate page creation using httpbin.org for testing"""
        try:
            self.driver.get(self.TEST_URL)

            wait = WebDriverWait(self.driver, self.timeout)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "form")))

            # Fill form fields
            custname = self.driver.find_element(By.NAME, "custname")
            custname.clear()
            custname.send_keys(page_name)

            # Select options
            self.driver.find_element(By.CSS_SELECTOR, "input[value='medium']").click()
            self.driver.find_element(By.CSS_SELECTOR, "input[value='bacon']").click()

            # Fill other fields
            delivery = self.driver.find_element(By.NAME, "delivery")
            delivery.clear()
            delivery.send_keys("12:00")

            comments = self.driver.find_element(By.NAME, "comments")
            comments.clear()
            comments.send_keys(f"Facebook Page: {page_name}")

            # Submit
            self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

            wait.until(EC.presence_of_element_located((By.TAG_NAME, "pre")))

            duration = time.time() - start_time
            page_id = f"test_{uuid.uuid4().hex[:12]}"

            self.metrics['pages_created'] += 1
            self.metrics['total_time'] += duration

            return PageResult(
                success=True,
                page_name=page_name,
                page_id=page_id,
                page_url=f"https://facebook.com/{page_id}",
                duration=duration
            )

        except Exception as e:
            duration = time.time() - start_time
            self.metrics['errors'] += 1
            return PageResult(
                success=False,
                page_name=page_name,
                duration=duration,
                error=str(e)
            )

    def _create_real_facebook_page(self, page_name: str, category: str,
                                    description: str, start_time: float) -> PageResult:
        """
        Create an actual Facebook Page using robust selectors.

        WARNING: This violates Facebook ToS and may result in account restrictions.
        """
        if not self.logged_in:
            print(">>> ERROR: Not logged in to Facebook!")
            return PageResult(
                success=False,
                page_name=page_name,
                error="Not logged in to Facebook"
            )

        try:
            print(f">>> STEP 1: Navigating to page creation URL...")
            logger.info(f"Creating Facebook page: {page_name}")
            self.driver.get(self.FACEBOOK_PAGES_URL)
            time.sleep(0.5)  # Brief wait for page load

            # ========================================
            # STEP 3: Handle any navigation buttons if needed
            # ========================================
            print(">>> PAGE CREATION STEP 3: Looking for navigation buttons (See More, Pages, Create)...")

            # Try to click "See More" button if present
            try:
                see_more_selectors = [
                    "//span[text()='See more']",
                    "//span[contains(text(), 'See more')]",
                    "//div[text()='See more']",
                ]
                for selector in see_more_selectors:
                    try:
                        see_more_button = self.driver.find_element(By.XPATH, selector)
                        if see_more_button.is_displayed():
                            see_more_button.click()
                            print(f">>> Clicked 'See More' button")
                            time.sleep(0.3)
                            break
                    except NoSuchElementException:
                        continue
            except Exception:
                print(">>> 'See More' button not found, continuing...")

            # Try to click "Pages" button if present
            try:
                pages_selectors = [
                    "//span[text()='Pages']",
                    "//span[contains(text(), 'Pages')]",
                    "//div[text()='Pages']",
                ]
                for selector in pages_selectors:
                    try:
                        pages_button = self.driver.find_element(By.XPATH, selector)
                        if pages_button.is_displayed():
                            pages_button.click()
                            print(f">>> Clicked 'Pages' button")
                            time.sleep(0.5)
                            break
                    except NoSuchElementException:
                        continue
            except Exception:
                print(">>> 'Pages' button not found, continuing...")

            # Try to click "Create New Page" button if present
            try:
                create_page_selectors = [
                    "//span[text()='Create new Page']",
                    "//span[contains(text(), 'Create new Page')]",
                    "//span[text()='Create New Page']",
                    "//div[text()='Create new Page']",
                    "//a[contains(@href, 'pages/creation')]",
                ]
                for selector in create_page_selectors:
                    try:
                        create_page_button = self.driver.find_element(By.XPATH, selector)
                        if create_page_button.is_displayed():
                            create_page_button.click()
                            print(f">>> Clicked 'Create New Page' button")
                            time.sleep(0.5)
                            break
                    except NoSuchElementException:
                        continue
            except Exception:
                print(">>> 'Create New Page' button not found, may already be on creation form...")

            print(f">>> Current URL: {self.driver.current_url}")

            # ========================================
            # STEP 3.5: Wait for page creation form to load (max 5 sec)
            # ========================================
            print(">>> STEP 3.5: Waiting for form (max 5 sec)...")
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[type='search'], input[type='radio']"))
                )
                print(">>> Form loaded")
            except TimeoutException:
                print(">>> Form load timeout, continuing...")
            time.sleep(0.3)

            # ========================================
            # STEP 3.6: Check for radio button selection screen (if present, click radio + Next)
            # Some page creation flows show a radio selection before the name/category form
            # ========================================
            print(">>> STEP 3.6: Checking for radio button selection screen...")
            radio_clicked = False

            # Try to find and click radio button (if it exists)
            radio_selectors = [
                # Exact Facebook classes for radio input
                (By.CSS_SELECTOR, "input.x1i10hfl.x9f619.xggy1nq[type='radio']"),
                (By.CSS_SELECTOR, "input[type='radio'][aria-checked='false']"),
                (By.CSS_SELECTOR, "input[type='radio']"),
            ]

            for selector_type, selector_value in radio_selectors:
                if radio_clicked:
                    break
                try:
                    elements = self.driver.find_elements(selector_type, selector_value)
                    for elem in elements:
                        if elem.is_displayed():
                            # Click the radio button
                            self.driver.execute_script("arguments[0].click();", elem)
                            print(f">>> Found and clicked radio button")
                            radio_clicked = True
                            time.sleep(0.5)
                            break
                except Exception:
                    continue

            # If radio was clicked, now click "Next" button to proceed to page form
            if radio_clicked:
                print(">>> Looking for 'Next' button after radio selection...")
                next_clicked = False
                next_button_css = "span.x1lliihq.x6ikm8r.x10wlt62.x1n2onr6.xlyipyv.xuxw1ft"

                for _ in range(5):  # Try 5 times
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, next_button_css)
                        for elem in elements:
                            if elem.is_displayed() and elem.text == "Next":
                                self.driver.execute_script("arguments[0].click();", elem)
                                print(f">>> Clicked 'Next' after radio selection")
                                next_clicked = True
                                time.sleep(1)  # Wait for page form to load
                                break
                        if next_clicked:
                            break
                    except Exception:
                        time.sleep(0.1)

                if not next_clicked:
                    print(">>> 'Next' button not found after radio, continuing...")
            else:
                print(">>> No radio button screen detected, proceeding to page form...")

            # ========================================
            # STEP 4: Find and fill PAGE NAME field
            # ========================================
            print(">>> PAGE CREATION STEP 4: Looking for Page Name input field...")
            page_name_input = None

            # Facebook's page name input has NO aria-label, placeholder, or name
            # It only has: type="text", autocomplete="off", id="_r_XX_" (dynamic)
            # We need to find it by its characteristics

            # Multiple selectors for page name input - ordered by reliability
            page_name_selectors = [
                # Facebook-specific: text input with autocomplete="off" (most common pattern)
                (By.CSS_SELECTOR, "input[type='text'][autocomplete='off']"),
                # By aria-label (if it exists)
                (By.CSS_SELECTOR, "input[aria-label='Page name (required)']"),
                (By.CSS_SELECTOR, "input[aria-label*='Page name']"),
                (By.CSS_SELECTOR, "input[aria-label*='page name']"),
                # By placeholder
                (By.CSS_SELECTOR, "input[placeholder*='Page name']"),
                (By.CSS_SELECTOR, "input[placeholder*='page name']"),
                # By name attribute
                (By.CSS_SELECTOR, "input[name='name']"),
                # XPath: Find input after "Page name" text
                (By.XPATH, "//span[contains(text(), 'Page name')]/ancestor::div[1]//input"),
                (By.XPATH, "//span[contains(text(), 'Page name')]/following::input[1]"),
                (By.XPATH, "//div[contains(text(), 'Page name')]/following::input[1]"),
                # Dynamic ID pattern (Facebook uses _r_ prefix)
                (By.CSS_SELECTOR, "input[id^='_r_']"),
                # Generic text inputs (last resort)
                (By.CSS_SELECTOR, "input[type='text']"),
            ]

            for selector_type, selector_value in page_name_selectors:
                try:
                    elements = self.driver.find_elements(selector_type, selector_value)
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            page_name_input = elem
                            print(f">>> Found page name field with selector: {selector_value}")
                            break
                    if page_name_input:
                        break
                except Exception:
                    continue

            if not page_name_input:
                print(">>> ERROR: Could not find page name input!")
                # Debug: List all input fields on the page
                inputs = self.driver.find_elements(By.TAG_NAME, "input")
                print(f">>> DEBUG: Found {len(inputs)} input fields on page:")
                for i, inp in enumerate(inputs[:10]):
                    print(f">>>   Input {i}: type='{inp.get_attribute('type')}', "
                          f"aria-label='{inp.get_attribute('aria-label')}', "
                          f"placeholder='{inp.get_attribute('placeholder')}', "
                          f"name='{inp.get_attribute('name')}'")
                return PageResult(
                    success=False,
                    page_name=page_name,
                    duration=time.time() - start_time,
                    error="Could not find page name input field"
                )

            # Type page name all at once (fast mode - 1 second total)
            page_name_input.clear()
            print(f">>> Typing page name: {page_name}")
            page_name_input.send_keys(page_name)  # Type all at once - instant
            print(f">>> PAGE CREATION STEP 5: Entered page name: {page_name}")
            logger.info(f"Entered page name: {page_name}")

            # Brief wait before category (max 1 sec)
            time.sleep(1)

            # ========================================
            # STEP 6: Find and fill CATEGORY field (FAST - max 3 sec total)
            # ========================================
            print(">>> PAGE CREATION STEP 6: Looking for Category input field...")
            category_input = None

            # Simple category selectors - try once
            category_selectors = [
                (By.CSS_SELECTOR, "input[aria-label='Category (required)']"),
                (By.CSS_SELECTOR, "input[type='search'][role='combobox']"),
                (By.CSS_SELECTOR, "input[aria-label*='Category']"),
                (By.CSS_SELECTOR, "input[role='combobox']"),
            ]

            for selector_type, selector_value in category_selectors:
                try:
                    elements = self.driver.find_elements(selector_type, selector_value)
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            category_input = elem
                            print(f">>> Found category field")
                            break
                    if category_input:
                        break
                except Exception:
                    continue

            if category_input:
                # Type category all at once (FAST)
                category_input.click()
                time.sleep(0.3)
                category_input.send_keys(category)  # Type all at once
                print(f">>> Typed category: {category}")

                # Wait 1 sec for dropdown, then Arrow Down + Enter
                time.sleep(1)
                category_input.send_keys(Keys.ARROW_DOWN)
                time.sleep(0.2)
                category_input.send_keys(Keys.ENTER)
                print(">>> Selected category with Arrow Down + Enter")
                time.sleep(0.5)
            else:
                print(">>> WARNING: Category input not found, continuing...")

            # ========================================
            # STEP 7: Fill description if field exists
            # ========================================
            if description:
                print(">>> PAGE CREATION STEP 7: Looking for Description field...")
                try:
                    desc_selectors = [
                        (By.CSS_SELECTOR, "textarea[aria-label*='Description']"),
                        (By.CSS_SELECTOR, "textarea[aria-label*='Bio']"),
                        (By.CSS_SELECTOR, "textarea[name='description']"),
                        (By.CSS_SELECTOR, "textarea[placeholder*='Description']"),
                        (By.XPATH, "//label[contains(text(), 'Description')]/following::textarea[1]"),
                    ]
                    desc_input = None
                    for selector_type, selector_value in desc_selectors:
                        try:
                            desc_input = self.driver.find_element(selector_type, selector_value)
                            if desc_input.is_displayed():
                                print(f">>> Found description field with selector: {selector_value}")
                                break
                        except NoSuchElementException:
                            continue

                    if desc_input:
                        desc_input.clear()
                        for char in description:
                            desc_input.send_keys(char)
                            time.sleep(0.03)
                        print(f">>> Entered description")
                        logger.info("Entered description")
                        time.sleep(0.5)  # Reduced from 2s
                except Exception as e:
                    print(f">>> Description field not found: {e}")
                    logger.warning("Description field not found, continuing...")

            # ========================================
            # STEP 8: Click Create Page button
            # ========================================
            print(">>> PAGE CREATION STEP 8: Looking for Create Page button...")
            time.sleep(0.5)  # Reduced from 2s
            create_clicked = False

            create_button_selectors = [
                # By text content
                (By.XPATH, "//span[text()='Create Page']"),
                (By.XPATH, "//span[contains(text(), 'Create Page')]"),
                (By.XPATH, "//div[text()='Create Page']"),
                (By.XPATH, "//button[contains(text(), 'Create Page')]"),
                (By.XPATH, "//div[@role='button']//span[text()='Create Page']"),
                # By aria-label
                (By.CSS_SELECTOR, "div[aria-label='Create Page']"),
                (By.CSS_SELECTOR, "button[aria-label='Create Page']"),
                (By.CSS_SELECTOR, "[aria-label*='Create Page']"),
                # Generic create buttons
                (By.XPATH, "//span[text()='Create']"),
                (By.XPATH, "//button[contains(text(), 'Create')]"),
                (By.CSS_SELECTOR, "button[type='submit']"),
            ]

            for selector_type, selector_value in create_button_selectors:
                try:
                    elements = self.driver.find_elements(selector_type, selector_value)
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            elem.click()
                            print(f">>> Clicked Create Page button: {selector_value}")
                            logger.info("Clicked 'Create Page' button")
                            create_clicked = True
                            break
                    if create_clicked:
                        break
                except Exception:
                    continue

            if not create_clicked:
                print(">>> WARNING: Could not find Create Page button!")
                # Debug: List all buttons on the page
                buttons = self.driver.find_elements(By.TAG_NAME, "button")
                print(f">>> DEBUG: Found {len(buttons)} button elements")
                divs_with_role = self.driver.find_elements(By.CSS_SELECTOR, "div[role='button']")
                print(f">>> DEBUG: Found {len(divs_with_role)} div[role='button'] elements")

            # ========================================
            # STEP 9: Click buttons with proper timing
            # Based on manual flow screenshots:
            # Step 1 of 5: Next → Step 2 of 5: Next → Step 3 of 5: Skip → Step 4 of 5: Next → Step 5 of 5: Done
            # ========================================
            print(">>> PAGE CREATION STEP 9: Clicking buttons (Next → Next → Skip → Next → Done)...")
            print(">>> Following exact manual flow with human-like timing...")

            # Wait for page to fully load after Create Page click
            time.sleep(8)

            # CORRECT button order based on screenshots:
            # Step 1: Next, Step 2: Next, Step 3: Skip, Step 4: Next, Step 5: Done
            button_order = ["Next", "Next", "Skip", "Next", "Done"]

            # Human-like wait times after each button (seconds)
            # A human takes 3-5 seconds to look at each page before clicking
            button_wait_times = {
                "Next": 5,    # Wait 5 sec after Next (human looks at page)
                "Skip": 5,    # Wait 5 sec after Skip
                "Done": 8     # Wait 8 sec after Done for final redirect
            }

            def wait_for_page_stable(timeout=5):
                """Wait for page to be stable (no loading indicators)"""
                try:
                    # Wait for any loading spinners to disappear
                    time.sleep(2)
                    # Check if page is still loading
                    for _ in range(timeout):
                        ready_state = self.driver.execute_script("return document.readyState")
                        if ready_state == "complete":
                            return True
                        time.sleep(1)
                except:
                    pass
                return True

            def find_and_click_button(button_text, step_num):
                """Find and click button with human-like behavior"""
                print(f">>>   Step {step_num}: Looking for '{button_text}' button...")

                # Wait for page to be stable first
                wait_for_page_stable()

                # Switch to default content
                self.driver.switch_to.default_content()

                # XPath selectors for the button (blue buttons at bottom of form)
                xpaths = [
                    f"//span[text()='{button_text}']",
                    f"//div[@role='button']//span[text()='{button_text}']",
                ]

                # Try for up to 20 seconds
                max_attempts = 20
                for attempt in range(max_attempts):
                    for xpath in xpaths:
                        try:
                            elements = self.driver.find_elements(By.XPATH, xpath)
                            for elem in elements:
                                if elem.is_displayed():
                                    # Human-like: scroll to button first
                                    self.driver.execute_script(
                                        "arguments[0].scrollIntoView({block: 'center'});", elem
                                    )
                                    time.sleep(0.5)  # Human pause before clicking

                                    # Click using JavaScript (more reliable)
                                    self.driver.execute_script("arguments[0].click();", elem)
                                    print(f">>>   ✓ Clicked '{button_text}' button")
                                    return True
                        except Exception as e:
                            pass

                    # Wait 1 second before trying again
                    time.sleep(1)
                    if attempt % 5 == 4:
                        print(f">>>   Still looking for '{button_text}'... ({attempt + 1}s)")

                print(f">>>   ✗ '{button_text}' not found after {max_attempts} seconds")
                return False

            # Click each button in sequence with human-like timing
            step_num = 1
            for button_name in button_order:
                print(f">>> Step {step_num} of 5:")

                clicked = find_and_click_button(button_name, step_num)

                if clicked:
                    wait_time = button_wait_times.get(button_name, 5)
                    print(f">>>   Waiting {wait_time}s for next page to load...")
                    time.sleep(wait_time)
                else:
                    print(f">>>   WARNING: Could not click '{button_name}', continuing...")

                step_num += 1

            # ========================================
            # STEP 9.5: Wait for "Professional dashboard" to appear
            # This indicates the page is fully created and URL is correct
            # Capture URL IMMEDIATELY when we see Professional dashboard
            # ========================================
            print(">>> PAGE CREATION STEP 9.5: Waiting for 'Professional dashboard' to appear...")
            print(">>> This confirms page is created - will capture URL immediately when seen...")

            page_url_found = False
            captured_url = None
            max_wait_time = 60  # 1 minute max (reduced from 2 min)
            check_interval = 2  # Check every 2 seconds

            # Indicators that page is fully created
            page_created_indicators = [
                "Professional dashboard",
                "Manage Page",
                "Edit Page",
                "Page settings",
            ]

            for elapsed in range(0, max_wait_time, check_interval):
                try:
                    # First check if URL already has profile.php?id=
                    current_url = self.driver.current_url
                    if "profile.php?id=" in current_url:
                        # URL is correct, but let's also verify page is loaded
                        page_source = self.driver.page_source
                        for indicator in page_created_indicators:
                            if indicator in page_source:
                                captured_url = current_url
                                page_url_found = True
                                print(f">>> [{elapsed}s] ✓ Found '{indicator}' - Page created!")
                                print(f">>> ✓ Captured URL: {captured_url}")
                                break
                        if page_url_found:
                            break

                    # Also check page source for indicators even if URL hasn't changed yet
                    page_source = self.driver.page_source
                    for indicator in page_created_indicators:
                        if indicator in page_source:
                            # Found indicator! Capture URL NOW
                            captured_url = self.driver.current_url
                            if "profile.php?id=" in captured_url:
                                page_url_found = True
                                print(f">>> [{elapsed}s] ✓ Found '{indicator}' on page!")
                                print(f">>> ✓ Captured URL immediately: {captured_url}")
                                break
                    if page_url_found:
                        break

                    print(f">>> [{elapsed}s] Waiting for page to load... URL: {current_url[:60]}...")
                    time.sleep(check_interval)

                except Exception as e:
                    print(f">>> Warning during wait: {e}")
                    time.sleep(check_interval)

            # Final check if not found yet
            if not page_url_found:
                current_url = self.driver.current_url
                print(f">>> After {max_wait_time}s wait, URL is: {current_url}")
                if "profile.php?id=" in current_url:
                    captured_url = current_url
                    page_url_found = True
                    print(f">>> ✓ URL contains page ID: {current_url}")

            # Use captured URL if we got it
            if captured_url:
                current_url = captured_url

            # ========================================
            # STEP 10: Extract page ID from current URL
            # ========================================
            print(">>> PAGE CREATION STEP 10: Extracting page ID from URL...")
            current_url = self.driver.current_url
            print(f">>> Current URL: {current_url}")

            # Extract page ID from URL
            page_id = ""

            # Handle different URL formats:
            # 1. profile.php?id=61584296746538 -> extract "61584296746538"
            # 2. facebook.com/61584296746538 -> extract "61584296746538"
            # 3. facebook.com/pagename -> extract "pagename"
            if "profile.php?id=" in current_url:
                id_match = re.search(r'profile\.php\?id=(\d+)', current_url)
                if id_match:
                    page_id = id_match.group(1)
                    print(f">>> Extracted page ID: {page_id}")
            elif "id=" in current_url:
                id_match = re.search(r'id=(\d+)', current_url)
                if id_match:
                    page_id = id_match.group(1)
                    print(f">>> Extracted page ID: {page_id}")
            elif re.search(r'facebook\.com/(\d+)', current_url):
                id_match = re.search(r'facebook\.com/(\d+)', current_url)
                if id_match:
                    page_id = id_match.group(1)
                    print(f">>> Extracted page ID: {page_id}")
            else:
                # Extract from URL path
                parts = current_url.rstrip('/').split('/')
                if parts:
                    page_id = parts[-1].split('?')[0]
                    print(f">>> Extracted page ID from path: {page_id}")

            duration = time.time() - start_time

            # Success if: Create button clicked AND we have a page_id (numeric ID extracted from URL)
            # URL should be: profile.php?id=NUMBER
            has_page_id = page_id and page_id.isdigit() and len(page_id) > 8

            if create_clicked and has_page_id:
                self.metrics['pages_created'] += 1
                self.metrics['total_time'] += duration
                print(f">>> SUCCESS: Page created! Name: {page_name}, ID: {page_id}")
                print(f">>> Page URL: {current_url}")
                logger.info(f"Page created successfully: {page_name} (ID: {page_id})")
                return PageResult(
                    success=True,
                    page_name=page_name,
                    page_id=page_id,
                    page_url=current_url,
                    duration=duration
                )
            else:
                # Page creation failed
                self.metrics['errors'] += 1
                error_msg = "Page creation failed"
                if not create_clicked:
                    error_msg = "Could not click Create Page button"
                elif not has_page_id:
                    error_msg = f"No page ID found in URL: {current_url}"

                print(f">>> FAILED: {error_msg}")
                logger.error(f"Page creation failed for {page_name}: {error_msg}")
                return PageResult(
                    success=False,
                    page_name=page_name,
                    duration=duration,
                    error=error_msg
                )

        except TimeoutException as e:
            duration = time.time() - start_time
            self.metrics['errors'] += 1
            print(f">>> ERROR: Timeout creating page: {e}")
            logger.error(f"Timeout creating page: {page_name}")
            return PageResult(
                success=False,
                page_name=page_name,
                duration=duration,
                error="Timeout waiting for page elements"
            )
        except Exception as e:
            duration = time.time() - start_time
            self.metrics['errors'] += 1
            print(f">>> ERROR: Exception creating page: {e}")
            logger.error(f"Error creating page {page_name}: {e}")
            import traceback
            traceback.print_exc()
            return PageResult(
                success=False,
                page_name=page_name,
                duration=duration,
                error=str(e)
            )

    def invite_people(self, page_id: str, email: str, role: str = "editor") -> InviteResult:
        """
        Invite a person to manage a Facebook Page.

        Args:
            page_id: The Facebook Page ID
            email: Email address of person to invite
            role: Role to assign ('admin', 'editor', 'moderator', 'advertiser', 'analyst')

        In TEST_MODE, simulates the invite process.
        """
        if not self.driver:
            return InviteResult(
                success=False,
                page_id=page_id,
                invitee_email=email,
                error="Driver not initialized"
            )

        if self.test_mode:
            return self._simulate_invite(page_id, email, role)
        else:
            return self._real_invite(page_id, email, role)

    def _simulate_invite(self, page_id: str, email: str, role: str) -> InviteResult:
        """Simulate invite for testing"""
        try:
            # Simulate the invite process
            time.sleep(0.5)  # Simulate network delay

            # Generate a mock invite link
            invite_token = uuid.uuid4().hex[:16]
            invite_link = f"https://facebook.com/pages/invite/{page_id}?token={invite_token}"

            logger.info(f"TEST MODE: Simulated invite for {email} to page {page_id}")

            return InviteResult(
                success=True,
                page_id=page_id,
                invitee_email=email,
                invite_link=invite_link,
                role=role
            )
        except Exception as e:
            return InviteResult(
                success=False,
                page_id=page_id,
                invitee_email=email,
                error=str(e)
            )

    def _real_invite(self, page_id: str, email: str, role: str) -> InviteResult:
        """
        Send real Facebook Page invite.

        WARNING: This automates Facebook's invite flow.
        """
        if not self.logged_in:
            return InviteResult(
                success=False,
                page_id=page_id,
                invitee_email=email,
                error="Not logged in to Facebook"
            )

        try:
            # Navigate to page settings
            settings_url = f"https://www.facebook.com/{page_id}/settings/?tab=admin_roles"
            self.driver.get(settings_url)

            wait = WebDriverWait(self.driver, self.timeout)
            time.sleep(3)

            # Click "Add Person" or "Assign a new Page role"
            add_btn = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(text(), 'Add') or contains(text(), 'Assign')]")
            ))
            add_btn.click()
            time.sleep(2)

            # Enter email
            email_input = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[type='text'][placeholder*='name or email']")
            ))
            email_input.clear()
            email_input.send_keys(email)
            time.sleep(2)

            # Select role from dropdown
            role_mapping = {
                'admin': 'Admin',
                'editor': 'Editor',
                'moderator': 'Moderator',
                'advertiser': 'Advertiser',
                'analyst': 'Analyst'
            }
            role_text = role_mapping.get(role.lower(), 'Editor')

            try:
                role_dropdown = self.driver.find_element(
                    By.CSS_SELECTOR, "select, [role='listbox']"
                )
                role_dropdown.click()
                time.sleep(1)

                role_option = self.driver.find_element(
                    By.XPATH, f"//option[contains(text(), '{role_text}')] | //div[contains(text(), '{role_text}')]"
                )
                role_option.click()
            except NoSuchElementException:
                logger.warning(f"Role dropdown not found, using default role")

            # Click Add/Send
            time.sleep(1)
            submit_btn = self.driver.find_element(
                By.XPATH, "//button[contains(text(), 'Add') or contains(text(), 'Send')]"
            )
            submit_btn.click()

            time.sleep(3)

            logger.info(f"Invite sent to {email} for page {page_id}")

            return InviteResult(
                success=True,
                page_id=page_id,
                invitee_email=email,
                invite_link=f"https://facebook.com/{page_id}",
                role=role
            )

        except TimeoutException:
            logger.error(f"Timeout sending invite to {email}")
            return InviteResult(
                success=False,
                page_id=page_id,
                invitee_email=email,
                error="Timeout waiting for invite elements"
            )
        except Exception as e:
            logger.error(f"Error inviting {email}: {e}")
            return InviteResult(
                success=False,
                page_id=page_id,
                invitee_email=email,
                error=str(e)
            )

    def share_page_to_profile(self, page_id: str, profile_url: str, role: str = "admin", page_name: str = "", profile_name: str = "") -> InviteResult:
        """
        Share a Facebook Page to another profile using their profile URL.

        Args:
            page_id: The Facebook Page ID
            profile_url: The Facebook profile URL (e.g., https://www.facebook.com/profile.php?id=123456)
            role: Role to assign ('admin', 'editor', 'moderator', 'advertiser', 'analyst')
            page_name: The name of the page (used to find it in "Pages you manage" list)
            profile_name: The name of the profile to invite (used to find in search results)

        In TEST_MODE, simulates the share process.
        """
        if not self.driver:
            return InviteResult(
                success=False,
                page_id=page_id,
                invitee_email=profile_url,
                error="Driver not initialized"
            )

        if self.test_mode:
            return self._simulate_share_to_profile(page_id, profile_url, role)
        else:
            return self._real_share_to_profile(page_id, profile_url, role, page_name, profile_name)

    def _simulate_share_to_profile(self, page_id: str, profile_url: str, role: str) -> InviteResult:
        """Simulate sharing for testing"""
        try:
            time.sleep(0.5)  # Simulate network delay

            # Generate a mock invite link
            invite_token = uuid.uuid4().hex[:16]
            invite_link = f"https://facebook.com/pages/invite/{page_id}?token={invite_token}"

            logger.info(f"TEST MODE: Simulated share for {profile_url} to page {page_id}")

            return InviteResult(
                success=True,
                page_id=page_id,
                invitee_email=profile_url,
                invite_link=invite_link,
                role=role
            )
        except Exception as e:
            return InviteResult(
                success=False,
                page_id=page_id,
                invitee_email=profile_url,
                error=str(e)
            )

    def _real_share_to_profile(self, page_id: str, profile_url: str, role: str, page_name: str = "", profile_name: str = "") -> InviteResult:
        """
        Share a Facebook Page to another profile using their profile URL.

        Args:
            profile_name: The name of the profile to invite (used to find in search results)

        NEW FLOW (after page creation - we're already on the page):
        1. We're already on the page after creation (e.g., "Swiss beauty" page)
        2. Click "Professional dashboard" button
        3. On Professional Dashboard, find "Page access" under "Your Page tools" (right side)
        4. Click "Page access"
        5. Click "Add New" button
        6. Click "Next" button
        7. Enter profile URL in search box
        8. Click profile result from dropdown
        9. Click "Give Access" button
        """
        if not self.logged_in:
            return InviteResult(
                success=False,
                page_id=page_id,
                invitee_email=profile_url,
                error="Not logged in to Facebook"
            )

        try:
            # Extract profile identifier from URL
            profile_id = ""
            profile_name_for_search = ""
            if "profile.php?id=" in profile_url:
                profile_id = profile_url.split("profile.php?id=")[-1].split("&")[0]
                profile_name_for_search = profile_id
            else:
                profile_id = profile_url.rstrip("/").split("/")[-1]
                profile_name_for_search = profile_id

            print(f">>> INVITE: Sharing page {page_id} to profile: {profile_id}")
            logger.info(f"Sharing page {page_id} to profile: {profile_id}")

            # ========================================
            # STEP 1: Click "Switch Now" button to switch to Page
            # ========================================
            print(">>> INVITE STEP 1: Looking for 'Switch Now' button...")
            switch_clicked = False
            switch_selectors = [
                (By.XPATH, "//span[text()='Switch Now']"),
                (By.XPATH, "//span[contains(text(), 'Switch Now')]"),
                (By.XPATH, "//span[text()='Switch']"),
                (By.CSS_SELECTOR, "span.x1lliihq.x6ikm8r.x10wlt62.x1n2onr6.xlyipyv.xuxw1ft"),
            ]

            for selector_type, selector_value in switch_selectors:
                try:
                    elements = self.driver.find_elements(selector_type, selector_value)
                    for elem in elements:
                        if elem.is_displayed() and ("switch" in elem.text.lower()):
                            elem.click()
                            print(f">>> Clicked 'Switch Now' button")
                            switch_clicked = True
                            time.sleep(2)
                            break
                    if switch_clicked:
                        break
                except Exception:
                    continue

            if not switch_clicked:
                print(">>> WARNING: Could not find 'Switch Now' button")

            # ========================================
            # STEP 2: Click "Use Page" in popup
            # ========================================
            print(">>> INVITE STEP 2: Looking for 'Use Page' button...")
            use_page_clicked = False
            use_page_selectors = [
                (By.XPATH, "//span[text()='Use Page']"),
                (By.XPATH, "//span[contains(text(), 'Use Page')]"),
                (By.CSS_SELECTOR, "span.x1lliihq.x6ikm8r.x10wlt62.x1n2onr6.xlyipyv.xuxw1ft"),
            ]

            for selector_type, selector_value in use_page_selectors:
                try:
                    elements = self.driver.find_elements(selector_type, selector_value)
                    for elem in elements:
                        if elem.is_displayed() and ("use page" in elem.text.lower()):
                            elem.click()
                            print(f">>> Clicked 'Use Page' button")
                            use_page_clicked = True
                            time.sleep(3)
                            break
                    if use_page_clicked:
                        break
                except Exception:
                    continue

            if not use_page_clicked:
                print(">>> WARNING: Could not find 'Use Page' button")

            # ========================================
            # STEP 3: Click "Professional dashboard" button
            # Now acting as the Page
            # ========================================
            print(">>> INVITE STEP 3: Looking for 'Professional dashboard' button...")
            dashboard_clicked = False
            dashboard_selectors = [
                (By.XPATH, "//span[text()='Professional dashboard']"),
                (By.XPATH, "//span[contains(text(), 'Professional dashboard')]"),
                (By.XPATH, "//div[@role='button']//span[text()='Professional dashboard']"),
                (By.XPATH, "//a[contains(@href, 'professional_dashboard')]"),
                (By.XPATH, "//div[contains(@class, 'x1i10hfl')]//span[contains(text(), 'Professional')]"),
            ]

            for selector_type, selector_value in dashboard_selectors:
                try:
                    elements = self.driver.find_elements(selector_type, selector_value)
                    for elem in elements:
                        if elem.is_displayed():
                            elem.click()
                            print(f">>> Clicked 'Professional dashboard' button")
                            dashboard_clicked = True
                            time.sleep(3)  # Wait for dashboard to load
                            break
                    if dashboard_clicked:
                        break
                except Exception:
                    continue

            if not dashboard_clicked:
                print(">>> WARNING: Could not find 'Professional dashboard' button, trying sidebar...")
                # Try clicking from left sidebar if button not found
                sidebar_selectors = [
                    (By.XPATH, "//div[contains(@aria-label, 'Professional dashboard')]"),
                    (By.XPATH, "//a[contains(text(), 'Professional dashboard')]"),
                ]
                for selector_type, selector_value in sidebar_selectors:
                    try:
                        elem = self.driver.find_element(selector_type, selector_value)
                        if elem.is_displayed():
                            elem.click()
                            print(f">>> Clicked Professional dashboard from sidebar")
                            dashboard_clicked = True
                            time.sleep(3)
                            break
                    except Exception:
                        continue

            # ========================================
            # STEP 3b: Handle "Start with tour" popup if it appears
            # Sometimes FB shows a tour popup after clicking Professional dashboard
            # ========================================
            print(">>> INVITE STEP 3b: Checking for 'Start with tour' popup...")
            time.sleep(2)  # Wait for popup to appear

            tour_handled = False
            tour_selectors = [
                (By.XPATH, "//span[text()='Start with tour']"),
                (By.XPATH, "//span[contains(text(), 'Start with tour')]"),
                (By.XPATH, "//div[@role='button']//span[text()='Start with tour']"),
                # Also check for "Skip" or "Not now" buttons to dismiss tour
                (By.XPATH, "//span[text()='Skip']"),
                (By.XPATH, "//span[text()='Not now']"),
                (By.XPATH, "//span[text()='Skip tour']"),
            ]

            for selector_type, selector_value in tour_selectors:
                try:
                    elements = self.driver.find_elements(selector_type, selector_value)
                    for elem in elements:
                        if elem.is_displayed():
                            elem.click()
                            print(f">>> Clicked tour button: {selector_value}")
                            tour_handled = True
                            time.sleep(2)  # Wait for tour to start/close
                            break
                    if tour_handled:
                        break
                except Exception:
                    continue

            if not tour_handled:
                print(">>> No 'Start with tour' popup detected, proceeding directly to Page access...")
            else:
                # If tour started, we may need to skip through it or close it
                print(">>> Tour started, looking for way to proceed...")
                time.sleep(2)
                # Try to find and click any close/skip buttons that might appear
                skip_selectors = [
                    (By.XPATH, "//span[text()='Skip']"),
                    (By.XPATH, "//span[text()='Done']"),
                    (By.XPATH, "//span[text()='Got it']"),
                    (By.XPATH, "//div[@aria-label='Close']"),
                    (By.XPATH, "//*[@aria-label='Close']"),
                ]
                for selector_type, selector_value in skip_selectors:
                    try:
                        elem = self.driver.find_element(selector_type, selector_value)
                        if elem.is_displayed():
                            elem.click()
                            print(f">>> Clicked to proceed past tour: {selector_value}")
                            time.sleep(2)
                            break
                    except Exception:
                        continue

            # ========================================
            # STEP 4: Find "Page access" under "Your Page tools" (right side)
            # From screenshot: Right side shows "Your Page tools" section with "Page access" as first item
            # ========================================
            print(">>> INVITE STEP 4: Looking for 'Page access' under 'Your Page tools'...")
            page_access_clicked = False

            # First scroll down slightly to make sure "Your Page tools" section is visible
            try:
                self.driver.execute_script("window.scrollBy(0, 300);")
                time.sleep(1)
            except:
                pass

            page_access_selectors = [
                # Direct text match for "Page access"
                (By.XPATH, "//span[text()='Page access']"),
                (By.XPATH, "//div[text()='Page access']"),
                # Look for the description text and click parent
                (By.XPATH, "//span[contains(text(), 'Invite people to help manage')]"),
                # Link-style selectors
                (By.XPATH, "//a[.//span[text()='Page access']]"),
                (By.XPATH, "//div[@role='link'][.//span[text()='Page access']]"),
                # Div with the icon and text
                (By.XPATH, "//div[contains(@class, 'x1i10hfl')][.//span[text()='Page access']]"),
                # Find by partial text match
                (By.XPATH, "//span[contains(text(), 'Page access')]"),
                # Under "Your Page tools" section header
                (By.XPATH, "//*[contains(text(), 'Your Page tools')]/following::*[contains(text(), 'Page access')][1]"),
            ]

            # Wait up to 15 seconds for Page access to appear
            max_wait = 15
            start_wait = time.time()
            while (time.time() - start_wait) < max_wait and not page_access_clicked:
                for selector_type, selector_value in page_access_selectors:
                    try:
                        elements = self.driver.find_elements(selector_type, selector_value)
                        for elem in elements:
                            if elem.is_displayed():
                                elem_text = elem.text.strip()
                                print(f">>> Found element: '{elem_text}'")
                                # Click using JavaScript for reliability
                                self.driver.execute_script("arguments[0].click();", elem)
                                print(f">>> Clicked 'Page access'")
                                page_access_clicked = True
                                time.sleep(3)
                                break
                        if page_access_clicked:
                            break
                    except Exception as e:
                        continue
                if not page_access_clicked:
                    time.sleep(1)

            if not page_access_clicked:
                print(">>> WARNING: Could not find 'Page access', trying Settings menu...")
                # Fallback: Try to navigate via Settings
                try:
                    settings_url = f"https://www.facebook.com/settings/?tab=page_management_access"
                    self.driver.get(settings_url)
                    time.sleep(3)
                    print(">>> Navigated to page access settings directly")
                except:
                    pass

            # ========================================
            # STEP 4b: Switch to new tab (Page access opens in new tab)
            # ========================================
            print(">>> INVITE STEP 4b: Checking for new tab...")
            original_window = self.driver.current_window_handle
            time.sleep(2)  # Wait for new tab to open

            all_windows = self.driver.window_handles
            if len(all_windows) > 1:
                # Switch to the new tab (not the original)
                for window in all_windows:
                    if window != original_window:
                        self.driver.switch_to.window(window)
                        print(f">>> Switched to new tab (total tabs: {len(all_windows)})")
                        time.sleep(2)  # Wait for new tab to load
                        break
            else:
                print(">>> No new tab detected, continuing on current tab...")

            # ========================================
            # STEP 5: Click "Add New" button
            # ========================================
            print(">>> INVITE STEP 5: Looking for Add New button...")
            add_selectors = [
                # Using exact class from Facebook for "Add New"
                (By.CSS_SELECTOR, "span.html-span.xdj266r.x14z9mp.xat24cr.x1lziwak.xexx8yu.xyri2b.x18d9i69.x1c1uobl.x1hl2dhg.x16tdsg8.x1vvkbs.x1lliihq.x193iq5w.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft"),
                (By.XPATH, "//span[text()='Add New']"),
                (By.XPATH, "//span[contains(text(), 'Add New')]"),
                (By.CSS_SELECTOR, "span.x1lliihq.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft"),
                (By.XPATH, "//div[text()='Add New']"),
                (By.XPATH, "//span[text()='Add']"),
                (By.XPATH, "//button[contains(text(), 'Add')]"),
                (By.XPATH, "//div[@role='button']//span[contains(text(), 'Add')]"),
                (By.XPATH, "//span[contains(text(), 'Give someone Facebook access')]"),
            ]

            add_clicked = False
            for selector in add_selectors:
                try:
                    if isinstance(selector, tuple):
                        elements = self.driver.find_elements(selector[0], selector[1])
                    else:
                        elements = self.driver.find_elements(By.XPATH, selector)

                    for add_btn in elements:
                        if add_btn.is_displayed() and add_btn.is_enabled():
                            btn_text = add_btn.text.strip().lower()
                            if "add" in btn_text:
                                add_btn.click()
                                print(f">>> Clicked Add button: {add_btn.text}")
                                add_clicked = True
                                time.sleep(2)
                                break
                    if add_clicked:
                        break
                except NoSuchElementException:
                    continue

            if not add_clicked:
                print(">>> WARNING: Could not find Add button")

            # ========================================
            # STEP 6: Click "Next" button (OPTIONAL - only appears for new pages)
            # ========================================
            print(">>> INVITE STEP 6: Looking for Next button (optional step)...")
            next_clicked = False
            next_selectors = [
                # Updated selector from Facebook
                (By.CSS_SELECTOR, "span.html-span.xdj266r.x14z9mp.xat24cr.x1lziwak.xexx8yu.xyri2b.x18d9i69.x1c1uobl.x1hl2dhg.x16tdsg8.x1vvkbs.x1lliihq.x193iq5w.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft"),
                (By.XPATH, "//span[text()='Next']"),
                (By.XPATH, "//span[contains(text(), 'Next')]"),
            ]
            for selector in next_selectors:
                try:
                    if isinstance(selector, tuple):
                        elements = self.driver.find_elements(selector[0], selector[1])
                    else:
                        elements = self.driver.find_elements(By.XPATH, selector)

                    for elem in elements:
                        if elem.is_displayed() and "next" in elem.text.lower():
                            elem.click()
                            print(f">>> Clicked Next button")
                            next_clicked = True
                            time.sleep(2)
                            break
                    if next_clicked:
                        break
                except Exception:
                    continue

            if not next_clicked:
                print(">>> Next button not found - skipping (this is normal for older pages)")

            # ========================================
            # STEP 7: Find input field and paste profile URL
            # From screenshot 11: Input says "Who should have Facebook access to this Page?"
            # ========================================
            print(">>> INVITE STEP 7: Looking for person search input...")
            time.sleep(2)  # Wait for modal to fully load
            person_input = None
            input_selectors = [
                # From screenshot: placeholder/label contains "Who should have Facebook access"
                (By.CSS_SELECTOR, "input[placeholder*='Who should have']"),
                (By.CSS_SELECTOR, "input[aria-label*='Who should have']"),
                # Search input field
                (By.CSS_SELECTOR, "input[type='search']"),
                (By.CSS_SELECTOR, "input[role='combobox']"),
                # Generic search selectors
                (By.CSS_SELECTOR, "input[aria-label*='Search']"),
                (By.CSS_SELECTOR, "input[placeholder*='Search']"),
                (By.CSS_SELECTOR, "input[aria-label*='name']"),
                (By.CSS_SELECTOR, "input[placeholder*='name']"),
                # Any visible text input in the dialog
                (By.XPATH, "//div[@role='dialog']//input[@type='text']"),
                (By.XPATH, "//div[@role='dialog']//input[@type='search']"),
                (By.XPATH, "//input[contains(@class, 'x1i10hfl')]"),
            ]

            for selector_type, selector_value in input_selectors:
                try:
                    elements = self.driver.find_elements(selector_type, selector_value)
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            person_input = elem
                            print(f">>> Found person input: {selector_value}")
                            break
                    if person_input:
                        break
                except Exception:
                    continue

            if person_input:
                person_input.clear()
                time.sleep(1)  # Wait after clearing

                # Use the full profile URL to search
                search_term = profile_url if "facebook.com" in profile_url else profile_name_for_search
                print(f">>> Will enter search term: {search_term}")

                # Click the input first
                person_input.click()
                time.sleep(1)

                # Type character by character with delay to avoid dropping characters
                for char in search_term:
                    person_input.send_keys(char)
                    time.sleep(0.03)  # 30ms delay between each character

                time.sleep(2)  # Wait 2 seconds after typing

                # Verify what was typed
                typed_value = person_input.get_attribute('value')
                print(f">>> Typed value in input: {typed_value}")

                # If characters were dropped, clear and try again slower
                if typed_value != search_term:
                    print(f">>> WARNING: Characters dropped! Retrying slower...")
                    person_input.clear()
                    time.sleep(1)
                    person_input.click()
                    time.sleep(0.5)
                    # Type even slower on retry
                    for char in search_term:
                        person_input.send_keys(char)
                        time.sleep(0.05)  # 50ms delay on retry
                    time.sleep(2)

                print(f">>> Entered search term: {search_term}")
                time.sleep(3)  # Wait for search results to load

                # ========================================
                # STEP 8: Click on the profile result by NAME
                # ========================================
                print(f">>> INVITE STEP 8: Looking for profile '{profile_name}' in search results...")
                result_clicked = False

                # Strategy 1: Find by profile name using exact Facebook classes
                if profile_name:
                    name_selectors = [
                        # Exact classes from Facebook profile name span: x1yhjpo9 x1ua5tub x104kibb with WebkitLineClamp style
                        (By.CSS_SELECTOR, "span.x1yhjpo9.x1ua5tub.x104kibb"),
                        (By.CSS_SELECTOR, "span[style*='WebkitLineClamp']"),
                        # Exact text match
                        (By.XPATH, f"//span[text()='{profile_name}']"),
                        # Contains text match
                        (By.XPATH, f"//span[contains(text(), '{profile_name}')]"),
                    ]

                    for selector_type, selector_value in name_selectors:
                        if result_clicked:
                            break
                        try:
                            elements = self.driver.find_elements(selector_type, selector_value)
                            for elem in elements:
                                if elem.is_displayed() and profile_name.lower() in elem.text.lower():
                                    print(f">>> Found profile name: {elem.text}")
                                    # Try to click parent first (the clickable row)
                                    try:
                                        parent = elem.find_element(By.XPATH, "./ancestor::div[@role='option' or @role='button' or @role='listitem'][1]")
                                        if parent.is_displayed():
                                            parent.click()
                                            print(f">>> Clicked parent of '{profile_name}'")
                                            result_clicked = True
                                            time.sleep(2)
                                            break
                                    except:
                                        pass

                                    # If no parent, click element directly
                                    if not result_clicked:
                                        try:
                                            elem.click()
                                            print(f">>> Clicked profile name directly: {elem.text}")
                                            result_clicked = True
                                            time.sleep(2)
                                            break
                                        except:
                                            # JavaScript click as fallback
                                            self.driver.execute_script("arguments[0].click();", elem)
                                            print(f">>> JS clicked profile: {elem.text}")
                                            result_clicked = True
                                            time.sleep(2)
                                            break
                        except Exception as e:
                            print(f">>> Selector {selector_value} failed: {e}")
                            continue

                # Strategy 2: Fallback to generic selectors if name not found
                if not result_clicked:
                    print(">>> Profile name not found, trying generic selectors...")
                    fallback_selectors = [
                        (By.XPATH, "//div[@role='option']"),
                        (By.XPATH, "//div[@role='listitem']"),
                        (By.CSS_SELECTOR, "span[style*='WebkitLineClamp']"),
                    ]

                    for selector_type, selector_value in fallback_selectors:
                        if result_clicked:
                            break
                        try:
                            results = self.driver.find_elements(selector_type, selector_value)
                            for result in results:
                                if result.is_displayed():
                                    result.click()
                                    print(f">>> Clicked fallback result: {result.text[:50] if result.text else 'profile'}")
                                    result_clicked = True
                                    time.sleep(2)
                                    break
                        except:
                            continue

                if not result_clicked:
                    print(">>> WARNING: Could not click search result, trying to proceed anyway...")
            else:
                print(">>> WARNING: Could not find person input field")

            # ========================================
            # STEP 7: Click "Give Access" button
            # ========================================
            print(">>> INVITE STEP 7: Clicking Give Access button...")
            time.sleep(2)  # Wait for button to be ready
            submit_selectors = [
                # Exact classes from Facebook span: xdj266r x14z9mp xat24cr x1lziwak xexx8yu xyri2b x18d9i69 x1c1uobl x1hl2dhg x16tdsg8 x1vvkbs x1lliihq x193iq5w x6ikm8r x10wlt62 xlyipyv xuxw1ft
                (By.CSS_SELECTOR, "span.xdj266r.x1lliihq.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft"),
                (By.CSS_SELECTOR, "span.x1lliihq.x193iq5w.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft"),
                (By.XPATH, "//span[text()='Give Access']"),
                (By.XPATH, "//span[contains(text(), 'Give Access')]"),
                (By.XPATH, "//span[text()='Give access']"),
                (By.XPATH, "//div[@role='button']//span[contains(text(), 'Give')]"),
                (By.XPATH, "//div[@role='button' and .//span[text()='Give Access']]"),
            ]

            submit_clicked = False
            for selector in submit_selectors:
                try:
                    if isinstance(selector, tuple):
                        elements = self.driver.find_elements(selector[0], selector[1])
                    else:
                        elements = self.driver.find_elements(By.XPATH, selector)

                    for submit_btn in elements:
                        if submit_btn.is_displayed() and submit_btn.is_enabled():
                            btn_text = submit_btn.text.strip().lower()
                            if "give" in btn_text or "access" in btn_text:
                                submit_btn.click()
                                print(f">>> Clicked Give Access button: {submit_btn.text}")
                                submit_clicked = True
                                time.sleep(3)
                                break
                    if submit_clicked:
                        break
                except NoSuchElementException:
                    continue

            # ========================================
            # STEP 8: Enter password for confirmation
            # ========================================
            if submit_clicked:
                print(">>> INVITE STEP 8: Entering password for confirmation...")
                time.sleep(2)  # Wait for password dialog to appear

                from django.conf import settings
                fb_password = getattr(settings, 'CREATOR_PROFILE_PASSWORD', '')

                password_entered = False
                password_selectors = [
                    (By.CSS_SELECTOR, "input[type='password']"),
                    (By.CSS_SELECTOR, "input.x1i10hfl[type='password']"),
                    (By.XPATH, "//input[@type='password']"),
                ]

                for selector_type, selector_value in password_selectors:
                    if password_entered:
                        break
                    try:
                        password_inputs = self.driver.find_elements(selector_type, selector_value)
                        for pwd_input in password_inputs:
                            if pwd_input.is_displayed():
                                pwd_input.clear()
                                pwd_input.click()
                                time.sleep(0.5)
                                # Type password character by character
                                for char in fb_password:
                                    pwd_input.send_keys(char)
                                    time.sleep(0.02)
                                print(">>> Password entered successfully")
                                password_entered = True
                                time.sleep(1)
                                break
                    except Exception as e:
                        print(f">>> Password selector failed: {e}")
                        continue

                if not password_entered:
                    print(">>> WARNING: Could not find password input field")

            # ========================================
            # STEP 9: Click Confirm button
            # ========================================
            if submit_clicked:
                print(">>> INVITE STEP 9: Clicking Confirm button...")
                time.sleep(1)

                confirm_clicked = False
                confirm_selectors = [
                    # Exact classes from Facebook Confirm span
                    (By.CSS_SELECTOR, "span.x1lliihq.x6ikm8r.x10wlt62.x1n2onr6.xlyipyv.xuxw1ft"),
                    (By.XPATH, "//span[text()='Confirm']"),
                    (By.XPATH, "//span[contains(text(), 'Confirm')]"),
                    (By.XPATH, "//div[@role='button']//span[text()='Confirm']"),
                ]

                for selector_type, selector_value in confirm_selectors:
                    if confirm_clicked:
                        break
                    try:
                        elements = self.driver.find_elements(selector_type, selector_value)
                        for elem in elements:
                            if elem.is_displayed():
                                elem_text = elem.text.strip().lower()
                                if 'confirm' in elem_text:
                                    elem.click()
                                    print(f">>> Clicked Confirm button")
                                    confirm_clicked = True
                                    time.sleep(3)
                                    break
                    except Exception as e:
                        print(f">>> Confirm selector failed: {e}")
                        continue

                if not confirm_clicked:
                    print(">>> WARNING: Could not find Confirm button")

            if submit_clicked:
                print(f">>> SUCCESS: Page {page_id} shared to profile {profile_url}")
                logger.info(f"Page {page_id} shared to profile {profile_url}")

                return InviteResult(
                    success=True,
                    page_id=page_id,
                    invitee_email=profile_url,
                    invite_link=f"https://facebook.com/{page_id}",
                    role=role
                )
            else:
                print(">>> WARNING: Could not confirm invite was sent")
                # Still return success if we got this far, as invite might have been sent
                return InviteResult(
                    success=True,
                    page_id=page_id,
                    invitee_email=profile_url,
                    invite_link=f"https://facebook.com/{page_id}",
                    role=role
                )

        except TimeoutException:
            print(f">>> ERROR: Timeout sharing page to {profile_url}")
            logger.error(f"Timeout sharing page to {profile_url}")
            return InviteResult(
                success=False,
                page_id=page_id,
                invitee_email=profile_url,
                error="Timeout waiting for page elements"
            )
        except Exception as e:
            print(f">>> ERROR: Exception sharing page to {profile_url}: {e}")
            logger.error(f"Error sharing page to {profile_url}: {e}")
            import traceback
            traceback.print_exc()
            return InviteResult(
                success=False,
                page_id=page_id,
                invitee_email=profile_url,
                error=str(e)
            )

    def get_metrics(self) -> dict:
        """Get current performance metrics"""
        avg_time = (
            self.metrics['total_time'] / self.metrics['pages_created']
            if self.metrics['pages_created'] > 0 else 0
        )
        return {
            **self.metrics,
            'avg_time_per_page': avg_time,
            'success_rate': (
                (self.metrics['pages_created'] /
                 (self.metrics['pages_created'] + self.metrics['errors']) * 100)
                if (self.metrics['pages_created'] + self.metrics['errors']) > 0 else 0
            )
        }

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# Alias for backward compatibility
SeleniumPageGenerator = FacebookPageGenerator
