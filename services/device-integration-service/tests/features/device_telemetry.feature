Feature: Smart device telemetry normalization
  As a FinanZen user
  I want readings from my connected devices to be normalized
  So that FinanZen can process telemetry consistently

  Scenario: Register a smart device connection
    Given user "user-1" has no registered device with id "smart-meter-001"
    When the user connects device "smart-meter-001" using provider "demo-provider"
    Then the device should be registered
    And the device status should be "active"

  Scenario: Normalize an energy consumption reading
    Given user "user-1" has an active device "smart-meter-001"
    When the device sends an energy consumption reading of 1500 Wh
    Then the reading should be normalized to 1.5 kWh
    And the validation status should be "valid"
    And the normalized reading should be stored in the telemetry store
    And a "ConsumptionReadingNormalized" event should be generated

  Scenario: Repeated telemetry reading is ignored
    Given a telemetry reading with source "smart-meter" and reading id "reading-001" has already been processed
    When the same telemetry reading is received again
    Then the reading should be ignored
    And no duplicate telemetry record should be stored
    And no duplicate "ConsumptionReadingNormalized" event should be generated

  Scenario: Reading from a revoked device is rejected
    Given user "user-1" has revoked device "smart-meter-001"
    When the revoked device sends a telemetry reading
    Then the reading should be rejected