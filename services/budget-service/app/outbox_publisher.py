import json
import os
import time

from kafka import KafkaProducer

from .repository import BudgetRepository


KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "localhost:9092",
)

TOPIC = "budget-threshold-reached"


def create_producer() -> KafkaProducer:
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        key_serializer=lambda value: value.encode("utf-8"),
    )


def run() -> None:
    repository = BudgetRepository(
        os.getenv(
            "FINANZEN_BUDGET_DB_PATH",
            "data/budgets.db",
        )
    )

    repository.initialize()

    producer = create_producer()

    print("FinanZen Budget Outbox Publisher started")

    while True:
        events = repository.list_pending_events()

        for event in events:
            try:
                producer.send(
                    TOPIC,
                    key=event["aggregate_id"],
                    value=event["payload"],
                ).get(timeout=10)

                repository.mark_event_as_published(event["id"])

                print(
                    f"Published {event['event_type']} "
                    f"{event['id']} to {TOPIC}"
                )

            except Exception as error:
                print(
                    f"Could not publish event {event['id']}: {error}"
                )

        time.sleep(2)


if __name__ == "__main__":
    run()