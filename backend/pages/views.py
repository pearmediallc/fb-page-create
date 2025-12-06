"""
API views for Facebook Page generation.
Uses in-memory storage as fallback when MongoDB is not available.
"""

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
import threading
import time
import random

# Try MongoDB first, fallback to in-memory storage
try:
    from .mongodb import (
        create_task,
        get_task,
        get_all_tasks,
        update_task_status,
        delete_task,
        get_pages_by_task,
        get_all_pages,
        store_profile,
        get_profile,
        get_all_profiles,
        get_efficiency_report,
        increment_task_counter,
        store_page_details,
        store_invite,
        get_invites_by_page,
        get_all_invites,
        update_invite_status,
        get_page_by_id,
    )
    from .mongodb import get_db
    get_db().command('ping')
    STORAGE_TYPE = "mongodb"
except Exception:
    from .storage import (
        create_task,
        get_task,
        get_all_tasks,
        update_task_status,
        delete_task,
        get_pages_by_task,
        get_all_pages,
        store_profile,
        get_profile,
        get_all_profiles,
        get_efficiency_report,
        increment_task_counter,
        store_page_details,
        store_invite,
        get_invites_by_page,
        get_all_invites,
        update_invite_status,
        get_page_by_id,
    )
    STORAGE_TYPE = "json_file"  # Data persists in pages/data.json

from automation.tasks import run_efficiency_test
from automation.name_generator import get_page_name_for_sequence


def run_task_sync(task_id: str):
    """
    Run page generation task synchronously in background thread.

    MULTI-PROFILE ROTATION FLOW:
    1. Login with first creator profile
    2. Create pages (up to PAGES_PER_PROFILE limit, default 3-4)
    3. After limit reached: logout → login with next profile
    4. Continue creating remaining pages
    5. Repeat until all pages created or all profiles exhausted

    This ensures we don't hit rate limits by rotating between profiles.
    """
    from automation.selenium_driver import FacebookPageGenerator
    from django.conf import settings

    task = get_task(task_id)
    if not task:
        return

    headless = getattr(settings, 'SELENIUM_HEADLESS', False)
    timeout = getattr(settings, 'SELENIUM_TIMEOUT', 30)
    test_mode = getattr(settings, 'SELENIUM_TEST_MODE', False)

    # Get pages per profile before rotation (default: 3)
    pages_per_profile = getattr(settings, 'PAGES_PER_PROFILE', 3)

    # Get list of creator profiles for rotation
    # Format: [{'email': 'x@x.com', 'password': 'xxx', 'name': 'Profile 1'}, ...]
    creator_profiles = getattr(settings, 'CREATOR_PROFILES', [])

    # Fallback to single profile if no rotation profiles configured
    if not creator_profiles:
        creator_email = getattr(settings, 'CREATOR_PROFILE_EMAIL', '')
        creator_password = getattr(settings, 'CREATOR_PROFILE_PASSWORD', '')
        if creator_email and creator_password:
            creator_profiles = [{
                'email': creator_email,
                'password': creator_password,
                'name': 'Default Profile',
                'pages_per_session': pages_per_profile
            }]

    # Get the public profile URL to share pages to (from the task/form)
    public_profile_url = task.get('public_profile_url', '')

    try:
        with FacebookPageGenerator(
            headless=headless,
            timeout=timeout,
            test_mode=test_mode,
            pages_per_profile=pages_per_profile
        ) as generator:

            # Set up multi-profile rotation
            if creator_profiles and not test_mode:
                generator.set_profiles(creator_profiles)
                print(f">>> MULTI-PROFILE MODE: {len(creator_profiles)} profiles configured")
                print(f">>> Pages per profile before rotation: {pages_per_profile}")

                # Login with first profile
                login_success = generator.login_with_rotation()
                if not login_success:
                    update_task_status(task_id, 'failed', error_message='Facebook login failed for all profiles')
                    return
            elif not test_mode:
                update_task_status(task_id, 'failed', error_message='No creator profiles configured')
                return

            # Track current profile for logging
            current_profile_email = generator.current_profile_email

            # Create pages with profile rotation
            for i in range(1, task['num_pages'] + 1):
                current = get_task(task_id)
                if current and current.get('status') == 'cancelled':
                    print(">>> Task cancelled by user")
                    break

                # Check if we should rotate to next profile before creating page
                if not test_mode and generator.should_rotate_profile():
                    print(f">>> ROTATION: Profile {current_profile_email} reached page limit")
                    rotation_status = generator.get_rotation_status()
                    print(f">>> Status: {rotation_status}")

                    if generator.has_more_profiles():
                        rotated = generator.rotate_to_next_profile()
                        if rotated:
                            current_profile_email = generator.current_profile_email
                            print(f">>> ROTATION: Switched to profile: {current_profile_email}")
                        else:
                            print(">>> ROTATION: Failed to rotate, continuing with current profile")
                    else:
                        print(">>> ROTATION: No more profiles available, continuing with current")

                # Generate page name with 70% female / 30% male distribution
                page_name, gender = get_page_name_for_sequence(
                    task['base_page_name'], i, task['num_pages']
                )

                print(f">>> [{current_profile_email}] Creating page {i}/{task['num_pages']}: {page_name}")

                # STEP 1: Create the page (now waits up to 120 sec for URL to stabilize)
                result = generator.create_facebook_page(page_name)

                if result.success:
                    # Track page count for rotation
                    generator.increment_page_count()

                    # STEP 2: Store page details with the correct URL
                    # store_page_details validates URL - returns None if invalid
                    stored_id = store_page_details(
                        task_id=task_id,
                        page_id=result.page_id,
                        page_name=result.page_name,
                        page_url=result.page_url,
                        sequence_num=i,
                        gender=gender
                    )

                    if stored_id:
                        # Page stored successfully with valid URL
                        increment_task_counter(task_id, 'pages_created')
                        print(f">>> ✓ Page '{page_name}' stored in database with ID: {result.page_id}")
                    else:
                        # URL was invalid - page not stored
                        increment_task_counter(task_id, 'pages_failed')
                        print(f">>> ✗ Page '{page_name}' NOT stored - invalid URL: {result.page_url}")
                        continue  # Skip to next page, don't try to share

                    # STEP 3: IMMEDIATELY share to profile (while still on the page)
                    # This is done right after page creation to avoid searching for the page later
                    if public_profile_url:
                        print(f">>> Immediately sharing page '{page_name}' to profile...")
                        invite_result = generator.share_page_to_profile(
                            page_id=result.page_id,
                            profile_url=public_profile_url,
                            role='admin',
                            page_name=result.page_name
                        )

                        if invite_result.success:
                            store_invite(
                                page_id=result.page_id,
                                page_name=result.page_name,
                                invitee_email=public_profile_url,
                                invite_link=invite_result.invite_link,
                                role='admin',
                                invited_by=current_profile_email
                            )
                            increment_task_counter(task_id, 'shares_sent')
                            print(f">>> Successfully shared page '{page_name}' to profile")
                        else:
                            increment_task_counter(task_id, 'shares_failed')
                            print(f">>> Failed to share page '{page_name}': {invite_result.error}")
                else:
                    # Page creation FAILED - immediately try next profile
                    print(f">>> FAILED to create page '{page_name}': {result.error}")

                    # Check for rate limit indicators in error message
                    error_lower = (result.error or "").lower()
                    is_rate_limit = any(phrase in error_lower for phrase in [
                        "too many", "rate limit", "try again later",
                        "temporarily blocked", "slow down", "limit reached"
                    ])

                    if is_rate_limit:
                        print(f">>> RATE LIMIT DETECTED: '{result.error}'")

                    # On ANY page creation failure, try rotating to next profile
                    if not test_mode and generator.has_more_profiles():
                        print(f">>> Page creation failed! Switching to next profile...")
                        rotated = generator.rotate_to_next_profile()
                        if rotated:
                            current_profile_email = generator.current_profile_email
                            print(f">>> Switched to profile: {current_profile_email}")

                            # RETRY creating the same page with new profile
                            print(f">>> RETRYING page '{page_name}' with new profile...")
                            retry_result = generator.create_facebook_page(page_name)

                            if retry_result.success:
                                generator.increment_page_count()
                                stored_id = store_page_details(
                                    task_id=task_id,
                                    page_id=retry_result.page_id,
                                    page_name=retry_result.page_name,
                                    page_url=retry_result.page_url,
                                    sequence_num=i,
                                    gender=gender
                                )
                                if stored_id:
                                    increment_task_counter(task_id, 'pages_created')
                                    print(f">>> ✓ RETRY SUCCESS: Page '{page_name}' created with new profile!")

                                    # Share to profile if URL provided
                                    if public_profile_url:
                                        invite_result = generator.share_page_to_profile(
                                            page_id=retry_result.page_id,
                                            profile_url=public_profile_url,
                                            role='admin',
                                            page_name=retry_result.page_name
                                        )
                                        if invite_result.success:
                                            store_invite(
                                                page_id=retry_result.page_id,
                                                page_name=retry_result.page_name,
                                                invitee_email=public_profile_url,
                                                invite_link=invite_result.invite_link,
                                                role='admin',
                                                invited_by=current_profile_email
                                            )
                                            increment_task_counter(task_id, 'shares_sent')
                                        else:
                                            increment_task_counter(task_id, 'shares_failed')
                                    continue  # Move to next page
                                else:
                                    increment_task_counter(task_id, 'pages_failed')
                            else:
                                # Retry also failed
                                increment_task_counter(task_id, 'pages_failed')
                                print(f">>> ✗ RETRY FAILED: Page '{page_name}' still couldn't be created")
                        else:
                            # Rotation failed
                            increment_task_counter(task_id, 'pages_failed')
                            print(f">>> No more profiles to try, marking page as failed")
                    else:
                        # No more profiles available or in test mode
                        increment_task_counter(task_id, 'pages_failed')
                        if not generator.has_more_profiles():
                            print(f">>> No more profiles available - cannot retry")

            # Log final rotation status
            if not test_mode:
                final_status = generator.get_rotation_status()
                print(f">>> TASK COMPLETE. Final rotation status: {final_status}")

        update_task_status(task_id, 'completed')
    except Exception as e:
        update_task_status(task_id, 'failed', error_message=str(e))


@api_view(['GET', 'POST'])
def tasks_list(request):
    if request.method == 'GET':
        tasks = get_all_tasks(limit=50)
        for task in tasks:
            total = task['num_pages']
            created = task.get('pages_created', 0)
            failed = task.get('pages_failed', 0)
            task['progress'] = round(((created + failed) / total) * 100, 1) if total > 0 else 0
            task['id'] = task.pop('_id')
        return Response(tasks)

    elif request.method == 'POST':
        page_name = request.data.get('page_name') or request.data.get('base_name')
        num_pages = request.data.get('num_pages') or request.data.get('count')

        if not page_name:
            return Response({'error': 'page_name is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not num_pages or num_pages < 1:
            return Response({'error': 'num_pages must be positive'}, status=status.HTTP_400_BAD_REQUEST)

        public_profile_url = request.data.get('public_profile_url', '')
        if not public_profile_url:
            return Response({'error': 'public_profile_url is required'}, status=status.HTTP_400_BAD_REQUEST)
        if 'facebook.com' not in public_profile_url:
            return Response({'error': 'public_profile_url must be a valid Facebook URL'}, status=status.HTTP_400_BAD_REQUEST)

        task_id = create_task(
            profile_id=request.data.get('profile_id', ''),
            num_pages=int(num_pages),
            page_name=page_name,
            public_profile_url=public_profile_url
        )

        task = get_task(task_id)
        task['id'] = task.pop('_id')
        task['progress'] = 0
        task['pages'] = []
        return Response(task, status=status.HTTP_201_CREATED)


@api_view(['GET', 'DELETE'])
def task_detail(request, task_id):
    task = get_task(task_id)
    if not task:
        return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        task['pages'] = get_pages_by_task(task_id)
        task['id'] = task.pop('_id')
        total = task['num_pages']
        created = task.get('pages_created', 0)
        failed = task.get('pages_failed', 0)
        task['progress'] = round(((created + failed) / total) * 100, 1) if total > 0 else 0
        return Response(task)

    elif request.method == 'DELETE':
        # Permanently delete the task and all associated pages/invites
        deleted = delete_task(task_id)
        if deleted:
            return Response({'message': 'Task permanently deleted'})
        else:
            return Response({'error': 'Failed to delete task'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
def task_start(request, task_id):
    task = get_task(task_id)
    if not task:
        return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)

    if task['status'] != 'pending':
        return Response({'error': f"Cannot start. Status: {task['status']}"}, status=status.HTTP_400_BAD_REQUEST)

    update_task_status(task_id, 'running')

    # Run in background thread
    thread = threading.Thread(target=run_task_sync, args=(task_id,))
    thread.daemon = True
    thread.start()

    task = get_task(task_id)
    task['id'] = task.pop('_id')
    task['progress'] = 0
    return Response(task)


@api_view(['POST'])
def task_cancel(request, task_id):
    task = get_task(task_id)
    if not task:
        return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)

    if task['status'] not in ['pending', 'running']:
        return Response({'error': 'Cannot cancel'}, status=status.HTTP_400_BAD_REQUEST)

    update_task_status(task_id, 'cancelled')
    task = get_task(task_id)
    task['id'] = task.pop('_id')
    return Response(task)


@api_view(['GET'])
def pages_list(request):
    return Response(get_all_pages(limit=100))


@api_view(['GET', 'POST'])
def profiles_list(request):
    if request.method == 'GET':
        return Response(get_all_profiles())

    email = request.data.get('email')
    password = request.data.get('password')
    if not email or not password:
        return Response({'error': 'email and password required'}, status=status.HTTP_400_BAD_REQUEST)

    profile_id = store_profile(email, password, request.data.get('name'))
    return Response({'id': profile_id, 'email': email}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
def efficiency_report(request):
    return Response(get_efficiency_report())


@api_view(['POST'])
def benchmark(request):
    base_name = request.data.get('base_name', 'BenchmarkPage')
    count = request.data.get('count', 5)
    headless = request.data.get('headless', True)
    timeout = request.data.get('timeout', 30)

    if not isinstance(count, int) or count < 1 or count > 50:
        return Response({'error': 'Count must be 1-50'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        results = run_efficiency_test(base_name=base_name, count=count, headless=headless, timeout=timeout)
        return Response(results)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def health_check(request):
    health = {'api': 'healthy', 'storage': STORAGE_TYPE, 'selenium': 'unknown'}

    try:
        from automation.selenium_driver import FacebookPageGenerator
        with FacebookPageGenerator(headless=True, timeout=10, test_mode=True) as gen:
            result = gen.create_facebook_page("HealthCheck")
            health['selenium'] = 'healthy' if result.success else f'failed: {result.error}'
    except Exception as e:
        health['selenium'] = f'error: {str(e)}'

    return Response(health)


# ===========================================
# Invite People Endpoints
# ===========================================

@api_view(['POST'])
def invite_person(request, page_id):
    """
    Invite a person to manage a Facebook Page.

    POST /api/pages/<page_id>/invite/
    {
        "email": "user@example.com",
        "role": "editor"  // admin, editor, moderator, advertiser, analyst
    }
    """
    email = request.data.get('email')
    role = request.data.get('role', 'editor')

    if not email:
        return Response({'error': 'email is required'}, status=status.HTTP_400_BAD_REQUEST)

    valid_roles = ['admin', 'editor', 'moderator', 'advertiser', 'analyst']
    if role.lower() not in valid_roles:
        return Response(
            {'error': f'Invalid role. Must be one of: {", ".join(valid_roles)}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get page info
    page = get_page_by_id(page_id)
    page_name = page['page_name'] if page else f"Page {page_id}"

    # Send invite via Selenium
    from automation.selenium_driver import FacebookPageGenerator
    from django.conf import settings

    headless = getattr(settings, 'SELENIUM_HEADLESS', True)
    timeout = getattr(settings, 'SELENIUM_TIMEOUT', 30)

    try:
        with FacebookPageGenerator(headless=headless, timeout=timeout, test_mode=True) as generator:
            result = generator.invite_people(page_id, email, role)

            if result.success:
                # Store invite record
                invite_id = store_invite(
                    page_id=page_id,
                    page_name=page_name,
                    invitee_email=email,
                    invite_link=result.invite_link,
                    role=role,
                    invited_by=request.data.get('invited_by', '')
                )

                return Response({
                    'success': True,
                    'invite_id': invite_id,
                    'page_id': page_id,
                    'email': email,
                    'role': role,
                    'invite_link': result.invite_link,
                    'message': f'Invite sent to {email}'
                }, status=status.HTTP_201_CREATED)
            else:
                return Response({
                    'success': False,
                    'error': result.error
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def page_invites(request, page_id):
    """Get all invites for a specific page"""
    invites = get_invites_by_page(page_id)
    return Response(invites)


@api_view(['GET'])
def invites_list(request):
    """Get all invites"""
    invites = get_all_invites(limit=100)
    return Response(invites)


@api_view(['POST'])
def accept_invite(request, invite_id):
    """Mark an invite as accepted"""
    update_invite_status(invite_id, 'accepted')
    return Response({'message': 'Invite accepted', 'status': 'accepted'})


@api_view(['POST'])
def decline_invite(request, invite_id):
    """Mark an invite as declined"""
    update_invite_status(invite_id, 'declined')
    return Response({'message': 'Invite declined', 'status': 'declined'})


@api_view(['POST'])
def test_invite_access(request):
    """
    Test the invite access flow for a given page and profile.

    POST /api/automation/test-invite/
    {
        "page_id": "61584296746538",
        "profile_url": "https://www.facebook.com/profile.php?id=61581753605988",
        "profile_name": "Marisse Dalton"
    }
    """
    page_id = request.data.get('page_id')
    profile_url = request.data.get('profile_url')
    profile_name = request.data.get('profile_name', '')

    if not page_id:
        return Response({'success': False, 'error': 'page_id is required'}, status=status.HTTP_400_BAD_REQUEST)
    if not profile_url:
        return Response({'success': False, 'error': 'profile_url is required'}, status=status.HTTP_400_BAD_REQUEST)
    if not profile_name:
        return Response({'success': False, 'error': 'profile_name is required'}, status=status.HTTP_400_BAD_REQUEST)

    from automation.selenium_driver import FacebookPageGenerator
    from django.conf import settings

    headless = getattr(settings, 'SELENIUM_HEADLESS', False)
    timeout = getattr(settings, 'SELENIUM_TIMEOUT', 30)
    creator_email = getattr(settings, 'CREATOR_PROFILE_EMAIL', '')
    creator_password = getattr(settings, 'CREATOR_PROFILE_PASSWORD', '')

    details_log = []

    try:
        with FacebookPageGenerator(headless=headless, timeout=timeout, test_mode=False) as generator:
            # Login first
            details_log.append("Step 1: Logging in to Facebook...")
            login_success = generator.login_facebook(email=creator_email, password=creator_password)

            if not login_success:
                return Response({
                    'success': False,
                    'error': 'Facebook login failed',
                    'details': '\n'.join(details_log)
                })
            details_log.append("Login successful!")

            # Navigate to the page
            page_url = f"https://www.facebook.com/profile.php?id={page_id}"
            details_log.append(f"Step 2: Navigating to page: {page_url}")
            generator.driver.get(page_url)
            time.sleep(3)
            details_log.append("Page loaded!")

            # Call share_page_to_profile
            details_log.append(f"Step 3: Starting invite access flow for profile: {profile_name} ({profile_url})")
            result = generator.share_page_to_profile(
                page_id=page_id,
                profile_url=profile_url,
                role='admin',
                page_name=f'Page {page_id}',
                profile_name=profile_name
            )

            if result.success:
                details_log.append("Invite access completed successfully!")
                return Response({
                    'success': True,
                    'message': 'Invite access sent successfully',
                    'details': '\n'.join(details_log)
                })
            else:
                details_log.append(f"Failed: {result.error}")
                return Response({
                    'success': False,
                    'error': result.error,
                    'details': '\n'.join(details_log)
                })

    except Exception as e:
        details_log.append(f"Exception: {str(e)}")
        return Response({
            'success': False,
            'error': str(e),
            'details': '\n'.join(details_log)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
