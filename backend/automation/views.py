from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .tasks import run_efficiency_test


@api_view(['POST'])
def benchmark(request):
    """
    Run a Selenium efficiency benchmark test.

    POST body:
    {
        "base_name": "TestPage",
        "count": 5,
        "headless": true,
        "timeout": 30
    }
    """
    base_name = request.data.get('base_name', 'BenchmarkPage')
    count = request.data.get('count', 5)
    headless = request.data.get('headless', True)
    timeout = request.data.get('timeout', 30)

    # Validate count
    if not isinstance(count, int) or count < 1 or count > 50:
        return Response(
            {'error': 'Count must be an integer between 1 and 50'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        results = run_efficiency_test(
            base_name=base_name,
            count=count,
            headless=headless,
            timeout=timeout
        )
        return Response(results)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def health_check(request):
    """Check if Selenium is properly configured"""
    from .selenium_driver import SeleniumPageGenerator

    try:
        with SeleniumPageGenerator(headless=True, timeout=10) as generator:
            result = generator.create_page("HealthCheck")
            return Response({
                'status': 'healthy',
                'selenium': 'working',
                'test_result': {
                    'success': result.success,
                    'duration': result.duration
                }
            })
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'selenium': 'failed',
            'error': str(e)
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
