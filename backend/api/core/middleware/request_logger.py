import json
import logging

logger = logging.getLogger(__name__)


class RequestResponseLoggerMiddleware:
    """Loga o body da requisição e da resposta no terminal para facilitar o debug em desenvolvimento."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Loga o body da requisição recebida
        self._log_request(request)

        response = self.get_response(request)

        # Loga o body da resposta apenas quando houver erro (4xx ou 5xx)
        if response.status_code >= 400:
            self._log_response(response)

        return response

    # Extrai e loga os dados da requisição de forma segura
    def _log_request(self, request):
        try:
            body = json.loads(request.body) if request.body else {}
            logger.debug(f"REQUEST [{request.method}] {request.path} — body: {body}")
        except Exception:
            logger.debug(f"REQUEST [{request.method}] {request.path} — body: (não parseável)")

    # Extrai e loga os dados da resposta de forma segura
    def _log_response(self, response):
        try:
            data = json.loads(response.content)
            logger.debug(f"RESPONSE [{response.status_code}] — body: {data}")
        except Exception:
            logger.debug(f"RESPONSE [{response.status_code}] — body: (não parseável)")
