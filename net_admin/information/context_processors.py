from django.conf import settings

def static_version(request):
    """
    정적 파일 캐시 버스팅을 위한 버전 정보를 모든 템플릿에 제공
    """
    return {
        'STATIC_VERSION': settings.STATIC_VERSION
    }
