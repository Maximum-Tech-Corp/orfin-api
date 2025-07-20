from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Handler customizado para tratar exceções da API.
    Converte ValidationError do Django em respostas REST adequadas.
    """
    if isinstance(exc, ValidationError):
        return Response(
            {'error': exc.message_dict if hasattr(
                exc, 'message_dict') else exc.messages},
            status=status.HTTP_400_BAD_REQUEST
        )

    return exception_handler(exc, context)
