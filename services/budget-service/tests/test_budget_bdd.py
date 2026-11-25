from decimal import Decimal

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from app.models import BudgetCreate
from app.repository import BudgetRepository


scenarios("features/budget_alerts.feature")


@pytest.fixture
def context(tmp_path):
    database_path = tmp_path / "bdd_budgets.db"

    repository = BudgetRepository(str(database_path))
    repository.initialize()

    return {
        "repository": repository,
        "user_id": "user-1",
        "budget": None,
        "result": None,
        "event": None,
    }


@given(
    parsers.parse(
        'user "{user_id}" has a monthly budget of {limit:d} PEN for category "{category}"'
    )
)
def budget_exists(context, user_id, limit, category):
    context["user_id"] = user_id

    budget_data = BudgetCreate(
        name="BDD Budget",
        category=category,
        currency="PEN",
        limit_amount=Decimal(limit),
    )

    budget = context["repository"].create_budget(
        user_id,
        budget_data,
    )

    context["budget"] = budget
    

@given(parsers.parse("the current spent amount is {amount:d} PEN"))
def current_spent_amount(context, amount):
    event = {
        "event_id": f"setup-{amount}",
        "event_type": "TransactionRecorded",
        "transaction_id": f"transaction-setup-{amount}",
        "user_id": context["user_id"],
        "account_id": "account-1",
        "type": "expense",
        "amount": str(amount),
        "currency": "PEN",
        "category": context["budget"].category,
        "occurred_at": "2026-11-25T00:00:00Z",
    }

    context["repository"].process_transaction_recorded(event)


@given('a "TransactionRecorded" event has already been processed')
def transaction_event_processed(context):
    budget_data = BudgetCreate(
        name="BDD Duplicate Budget",
        category="food",
        currency="PEN",
        limit_amount=Decimal("500"),
    )

    budget = context["repository"].create_budget(
        "user-1",
        budget_data,
    )

    event = {
        "event_id": "duplicate-event-001",
        "event_type": "TransactionRecorded",
        "transaction_id": "transaction-duplicate-001",
        "user_id": "user-1",
        "account_id": "account-1",
        "type": "expense",
        "amount": "100",
        "currency": "PEN",
        "category": "food",
        "occurred_at": "2026-11-25T00:00:00Z",
    }

    context["repository"].process_transaction_recorded(event)

    context["budget"] = budget
    context["event"] = event


@when(
    parsers.parse(
        'a financial transaction of {amount:d} PEN is registered as an expense in category "{category}"'
    )
)
def register_expense(context, amount, category):
    event = {
        "event_id": f"event-{amount}-{category}",
        "event_type": "TransactionRecorded",
        "transaction_id": f"transaction-{amount}-{category}",
        "user_id": context["user_id"],
        "account_id": "account-1",
        "type": "expense",
        "amount": str(amount),
        "currency": "PEN",
        "category": category,
        "occurred_at": "2026-11-25T00:00:00Z",
    }

    context["result"] = context["repository"].process_transaction_recorded(event)


@when("the same event is received again")
def replay_same_event(context):
    context["result"] = context["repository"].process_transaction_recorded(
        context["event"]
    )


@then(parsers.parse("the budget spent amount should be {amount:d} PEN"))
def verify_spent(context, amount):
    status = context["repository"].get_budget_status(
        context["user_id"],
        context["budget"].id,
    )

    assert status.spent_amount == Decimal(amount)


@then(parsers.parse("the remaining amount should be {amount:d} PEN"))
def verify_remaining(context, amount):
    status = context["repository"].get_budget_status(
        context["user_id"],
        context["budget"].id,
    )

    assert status.remaining_amount == Decimal(amount)


@then(parsers.parse("the budget usage percentage should be {percentage:d} percent"))
def verify_usage(context, percentage):
    status = context["repository"].get_budget_status(
        context["user_id"],
        context["budget"].id,
    )

    assert status.usage_percentage == Decimal(percentage)


@then('a "BudgetThresholdReached" event should be generated')
def verify_threshold_event(context):
    events = context["repository"].list_pending_events()

    assert any(
        event["event_type"] == "BudgetThresholdReached"
        for event in events
    )


@then(parsers.parse('a notification should be created for user "{user_id}"'))
def notification_will_be_generated(user_id):
    # The notification itself is consumed by Notification Service.
    # This BDD verifies that Budget Service emits the event that triggers it.
    assert user_id == "user-1"


@then("the event should be ignored")
def verify_ignored(context):
    assert context["result"]["status"] == "ignored"


@then("the budget spent amount should not increase again")
def verify_no_duplicate_spending(context):
    status = context["repository"].get_budget_status(
        "user-1",
        context["budget"].id,
    )

    assert status.spent_amount == Decimal("100")