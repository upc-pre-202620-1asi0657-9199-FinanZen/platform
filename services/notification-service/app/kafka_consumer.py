import json
import os

from kafka import KafkaConsumer

from .repository import NotificationRepository


KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "localhost:9092",
)

TOPIC = "budget-threshold-reached"


def create_consumer() -> KafkaConsumer:
    return KafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="notification-service",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda value: json.loads(
            value.decode("utf-8")
        ),
        key_deserializer=lambda value: (
            value.decode("utf-8") if value else None
        ),
    )


def run() -> None:
    repository = NotificationRepository(
        os.getenv(
            "FINANZEN_NOTIFICATION_DB_PATH",
            "data/notifications.db",
        )
    )

    repository.initialize()

    consumer = create_consumer()

    print("FinanZen Notification Kafka Consumer started")

    for message in consumer:
        try:
            event = message.value

            result = repository.process_budget_threshold_reached(event)

            print(
                f"Processed event {event['event_id']}: "
                f"{result['status']}"
            )

        except Exception as error:
            print(f"Could not process event: {error}")


if __name__ == "__main__":
    run()