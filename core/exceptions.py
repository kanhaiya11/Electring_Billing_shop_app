from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        detail = response.data
        message = detail.get("detail", "Request failed") if isinstance(detail, dict) else "Request failed"
        response.data = {"success": False, "message": str(message), "errors": detail if isinstance(detail, dict) else {"detail": detail}}
    return response
