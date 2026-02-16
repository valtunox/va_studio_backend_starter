# import asyncio
# from services.notifications.service import NotificationService

from app.core.logger import get_logger
logger = get_logger(__name__)

# async def main():
#     """
#     Exemplo de como usar o NotificationService para enviar notifica\u00e7\u00f5es.
#     """
#     logger.info("Starting NotificationService example usage")
#     # Inicializa o servi\u00e7o de notifica\u00e7\u00e3o
#     notification_service = NotificationService()

#     # Exemplo de envio de uma notifica\u00e7\u00e3o
#     user_id = "user_123"
#     message = "Sua fatura de maio est\u00e1 dispon\u00edvel."

#     logger.info(f"Sending notification to user {user_id}: '{message}'")
#     await notification_service.send_notification(user_id, message)

#     # Em um aplicativo real, voc\u00ea pode querer manter o servi\u00e7o ativo
#     # para lidar com eventos e enviar mais notifica\u00e7\u00f5es.
#     # Por exemplo, voc\u00ea pode ter um loop de eventos ou um servidor em execu\u00e7\u00e3o.

#     # Para este exemplo, vamos apenas enviar uma notifica\u00e7\u00e3o e sair.
#     logger.info("Notification example completed")

# if __name__ == "__main__":
#     asyncio.run(main())
