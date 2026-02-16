import asyncio
import unittest
from unittest.mock import AsyncMock, patch
from services.notifications.service import NotificationService
from services.notifications.websocket import notification_websocket_endpoint

from app.core.logger import get_logger
logger = get_logger(__name__)

class TestNotificationService(unittest.TestCase):
    def setUp(self):
        self.service = NotificationService()
        self.user_id = "user_test"
        logger.info(f"Setting up TestNotificationService with user_id={self.user_id}")

    @patch("services.notifications.service.async_to_sync")
    def test_send_notification_successful(self, mock_async_to_sync):
        """
        Testa se a notifica\u00e7\u00e3o \u00e9 enviada com sucesso atrav\u00e9s do canal do usu\u00e1rio.
        """
        logger.info("Running test_send_notification_successful")
        # Configura\u00e7\u00e3o
        channel_layer = AsyncMock()
        self.service.channel_layer = channel_layer
        message = "Nova notifica\u00e7\u00e3o"

        # Execu\u00e7\u00e3o
        asyncio.run(self.service.send_notification(self.user_id, message))

        # Verifica\u00e7\u00e3o
        mock_async_to_sync.assert_called_with(channel_layer.group_send)
        logger.info("test_send_notification_successful passed")
        # A l\u00f3gica exata de como a mensagem \u00e9 constru\u00edda e enviada pode precisar de um teste mais detalhado
        # dependendo da implementa\u00e7\u00e3o de `async_to_sync` e `group_send`.

    async def test_websocket_endpoint_connection(self):
        """
        Testa a conex\u00e3o bem-sucedida ao endpoint do WebSocket de notifica\u00e7\u00e3o.
        """
        logger.info("Running test_websocket_endpoint_connection")
        # Configura\u00e7\u00e3o
        websocket = AsyncMock()

        # Execu\u00e7\u00e3o
        await notification_websocket_endpoint(websocket, self.user_id)

        # Verifica\u00e7\u00e3o
        websocket.accept.assert_called_once()
        logger.info("test_websocket_endpoint_connection passed")
        # O teste deve verificar se o websocket \u00e9 adicionado ao grupo correto
        # Isso pode exigir mocking do `channel_layer` se ele for usado diretamente no endpoint.

class TestNotificationModels(unittest.TestCase):
    # Se houver modelos de dados em `models.py`, adicione testes para eles aqui.
    # Exemplo:
    # def test_notification_model_creation(self):
    #     notification = Notification(id=1, user_id="user_123", message="Teste")
    #     self.assertEqual(notification.id, 1)
    #     self.assertEqual(notification.user_id, "user_123")
    #     self.assertEqual(notification.message, "Teste")
    pass

class TestNotificationTasks(unittest.TestCase):
    # Se houver tarefas do Celery em `tasks.py`, adicione testes para elas aqui.
    # Exemplo com mock do Celery:
    # @patch("services.notifications.tasks.send_push_notification.delay")
    # def test_send_push_notification_task(self, mock_delay):
    #     user_id = "user_456"
    #     message = "Push notification test"
    #     tasks.schedule_push_notification(user_id, message)
    #     mock_delay.assert_called_once_with(user_id, message)
    pass

if __name__ == "__main__":
    unittest.main()
