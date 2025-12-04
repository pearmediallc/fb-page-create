"""
Celery tasks for Facebook Page generation using Selenium.
Handles async batch processing and stores results in MongoDB.
"""

import time
import logging
from celery import shared_task
from django.conf import settings

from pages.mongodb import (
    get_task,
    update_task_status,
    increment_task_counter,
    store_page_details,
    get_profile,
)
from .selenium_driver import FacebookPageGenerator

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def create_pages_task(self, task_id: str):
    """
    Celery task to create multiple Facebook pages.

    Args:
        task_id: MongoDB ObjectId of the task document

    Returns:
        dict with execution results and metrics
    """
    logger.info(f"Starting page creation task: {task_id}")

    # Get task from MongoDB
    task = get_task(task_id)
    if not task:
        logger.error(f"Task not found: {task_id}")
        return {'error': f'Task {task_id} not found'}

    # Update task with Celery task ID
    update_task_status(task_id, 'running', celery_task_id=self.request.id)

    # Get profile credentials
    profile = get_profile(task['profile_id']) if task.get('profile_id') else None

    # Configuration
    headless = getattr(settings, 'SELENIUM_HEADLESS', True)
    timeout = getattr(settings, 'SELENIUM_TIMEOUT', 30)
    test_mode = True  # Set to False to use real Facebook (NOT RECOMMENDED)

    num_pages = task['num_pages']
    base_page_name = task['base_page_name']
    assigned_bm = task.get('assigned_bm', '')

    overall_start = time.time()
    results = {
        'task_id': task_id,
        'processed': 0,
        'success': 0,
        'failed': 0,
        'pages': []
    }

    try:
        with FacebookPageGenerator(
            headless=headless,
            timeout=timeout,
            test_mode=test_mode
        ) as generator:

            # Login if credentials provided and not in test mode
            if profile and not test_mode:
                login_success = generator.login_facebook(
                    email=profile['email'],
                    password=profile['password']
                )
                if not login_success:
                    update_task_status(task_id, 'failed',
                                       error_message='Facebook login failed')
                    return {'error': 'Facebook login failed'}

            # Create pages
            for i in range(1, num_pages + 1):
                # Check if task was cancelled
                current_task = get_task(task_id)
                if current_task and current_task.get('status') == 'cancelled':
                    logger.info(f"Task {task_id} was cancelled")
                    break

                page_name = f"{base_page_name}_{i}"
                logger.info(f"Creating page {i}/{num_pages}: {page_name}")

                # Create the page
                result = generator.create_facebook_page(
                    page_name=page_name,
                    category='Business',
                    description=f'{page_name} - Auto-generated page'
                )

                if result.success:
                    # Store page in MongoDB
                    store_page_details(
                        task_id=task_id,
                        page_id=result.page_id,
                        page_name=result.page_name,
                        page_url=result.page_url,
                        assigned_bm=assigned_bm,
                        sequence_num=i
                    )
                    increment_task_counter(task_id, 'pages_created')
                    results['success'] += 1
                else:
                    increment_task_counter(task_id, 'pages_failed')
                    results['failed'] += 1

                results['processed'] += 1
                results['pages'].append({
                    'name': page_name,
                    'page_id': result.page_id,
                    'page_url': result.page_url,
                    'success': result.success,
                    'duration': result.duration,
                    'error': result.error
                })

            # Get final metrics
            metrics = generator.get_metrics()
            results['metrics'] = metrics

    except Exception as e:
        logger.error(f"Task {task_id} failed with error: {e}")
        update_task_status(task_id, 'failed', error_message=str(e))
        results['error'] = str(e)
        return results

    # Update final task status
    total_time = time.time() - overall_start
    results['total_time'] = total_time

    final_status = 'completed' if results['failed'] == 0 else 'completed'
    if results['success'] == 0 and results['failed'] > 0:
        final_status = 'failed'

    update_task_status(task_id, final_status)

    logger.info(f"Task {task_id} completed: {results['success']} success, {results['failed']} failed")
    return results


@shared_task
def run_benchmark_task(base_name: str, count: int, headless: bool = True,
                       timeout: int = 30, test_mode: bool = True):
    """
    Celery task to run a Selenium benchmark test.

    Args:
        base_name: Base name for generated pages
        count: Number of pages to create
        headless: Whether to run browser in headless mode
        timeout: Selenium timeout in seconds
        test_mode: Use test site instead of real Facebook

    Returns:
        dict with benchmark results
    """
    logger.info(f"Starting benchmark: {count} pages with base name '{base_name}'")

    results = {
        'pages': [],
        'metrics': {}
    }

    start_time = time.time()

    try:
        with FacebookPageGenerator(
            headless=headless,
            timeout=timeout,
            test_mode=test_mode
        ) as generator:

            for i in range(1, count + 1):
                page_name = f"{base_name}_{i}"

                result = generator.create_facebook_page(page_name=page_name)

                results['pages'].append({
                    'name': page_name,
                    'page_id': result.page_id,
                    'success': result.success,
                    'duration': result.duration,
                    'error': result.error
                })

            results['metrics'] = generator.get_metrics()

    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        results['error'] = str(e)

    results['total_time'] = time.time() - start_time
    logger.info(f"Benchmark completed in {results['total_time']:.2f}s")

    return results


# Synchronous versions for direct API calls (non-Celery)
def run_page_generation_sync(task_id: str) -> dict:
    """
    Synchronous version of page generation (runs immediately).
    Use this for testing or when Celery is not available.
    """
    return create_pages_task(task_id)


def run_efficiency_test(base_name: str, count: int, headless: bool = True,
                        timeout: int = 30) -> dict:
    """
    Run a standalone efficiency test synchronously.
    """
    results = {
        'pages': [],
        'metrics': {}
    }

    start_time = time.time()

    with FacebookPageGenerator(
        headless=headless,
        timeout=timeout,
        test_mode=True
    ) as generator:

        for i in range(1, count + 1):
            page_name = f"{base_name}_{i}"
            result = generator.create_facebook_page(page_name=page_name)
            results['pages'].append({
                'name': page_name,
                'page_id': result.page_id,
                'success': result.success,
                'duration': result.duration,
                'error': result.error
            })

        results['metrics'] = generator.get_metrics()

    results['total_time'] = time.time() - start_time
    return results
