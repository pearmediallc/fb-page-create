"""
Test script for invite access functionality
"""
import sys
import os

# Add the project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from automation.selenium_driver import FacebookPageGenerator

# Test parameters
PAGE_URL = "https://www.facebook.com/profile.php?id=61584296746538"
PAGE_ID = "61584296746538"
PROFILE_TO_INVITE = "https://www.facebook.com/profile.php?id=61581753605988"

def test_invite():
    print("=" * 60)
    print("TESTING INVITE ACCESS")
    print("=" * 60)
    print(f"Page ID: {PAGE_ID}")
    print(f"Page URL: {PAGE_URL}")
    print(f"Profile to invite: {PROFILE_TO_INVITE}")
    print("=" * 60)

    # Initialize the generator (not headless so we can see what happens)
    with FacebookPageGenerator(headless=False, timeout=30, test_mode=False) as generator:
        # First login using saved cookies
        from django.conf import settings
        creator_email = getattr(settings, 'CREATOR_PROFILE_EMAIL', '')
        creator_password = getattr(settings, 'CREATOR_PROFILE_PASSWORD', '')

        print(f"\n>>> Logging in to Facebook...")
        login_success = generator.login_facebook(email=creator_email, password=creator_password)

        if not login_success:
            print(">>> ERROR: Login failed!")
            return

        print(">>> Login successful!")

        # Navigate to the page
        print(f"\n>>> Navigating to page: {PAGE_URL}")
        generator.driver.get(PAGE_URL)

        import time
        time.sleep(3)  # Wait for page to load

        # Now try to share to profile
        print(f"\n>>> Attempting to share page to profile...")
        result = generator.share_page_to_profile(
            page_id=PAGE_ID,
            profile_url=PROFILE_TO_INVITE,
            role='admin',
            page_name='Test Page'
        )

        print("\n" + "=" * 60)
        print("RESULT:")
        print("=" * 60)
        print(f"Success: {result.success}")
        print(f"Page ID: {result.page_id}")
        print(f"Invitee: {result.invitee_email}")
        if result.success:
            print(f"Invite Link: {result.invite_link}")
        else:
            print(f"Error: {result.error}")
        print("=" * 60)

if __name__ == "__main__":
    test_invite()
