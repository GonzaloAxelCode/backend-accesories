import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny

logger = logging.getLogger(__name__)


@api_view(["GET", "POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def whatsapp_webhook(request):
    """Webhook de Meta WhatsApp Cloud API.

    GET  -> verificación (hub.mode / hub.verify_token / hub.challenge).
    POST -> recepción de eventos (messages, statuses).
    URL pública: /api/whatsapp/webhook/
    """

    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == settings.WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(challenge)

        return HttpResponse("Forbidden", status=403)

    # POST
    logger.info("WhatsApp webhook POST: %s", request.data)
    print(request.data)

    return JsonResponse({"status": "ok"})
