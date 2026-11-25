Feature: Budget alerts after financial transactions
  As a FinanZen user
  I want my budgets to update when I register expenses
  So that I can receive alerts when I approach my spending limit

  Scenario: Expense updates the corresponding budget
    Given user "user-1" has a monthly budget of 500 PEN for category "food"
    When a financial transaction of 100 PEN is registered as an expense in category "food"
    Then the budget spent amount should be 100 PEN
    And the remaining amount should be 400 PEN
    And the budget usage percentage should be 20 percent

  Scenario: Expense reaching the threshold generates an alert
    Given user "user-1" has a monthly budget of 500 PEN for category "food"
    And the current spent amount is 100 PEN
    When a financial transaction of 350 PEN is registered as an expense in category "food"
    Then the budget usage percentage should be 90 percent
    And a "BudgetThresholdReached" event should be generated
    And a notification should be created for user "user-1"

  Scenario: Repeated transaction event is ignored
    Given a "TransactionRecorded" event has already been processed
    When the same event is received again
    Then the event should be ignored
    And the budget spent amount should not increase again