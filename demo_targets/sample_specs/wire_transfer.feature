Feature: Wire Transfer Compliance Flow
  As a QA engineer testing MockBank
  I want to verify the wire transfer submission flow
  So that compliance and selector stability are validated

  Scenario: Submit a standard wire transfer
    Given the user is on the MockBank wire transfer page
    When the user fills in Account Number "1234567890"
    And the user fills in SSN "123-45-6789"
    And the user fills in Amount "5000"
    And the user clicks "Confirm Transfer"
    Then the system shows a confirmation with reference "TXN-MOCK-001"

  Scenario: Self-healing after UI selector mutation
    Given the user is on the MockBank wire transfer page with chaos_mode enabled
    When the user fills in Account Number "9876543210"
    And the user fills in SSN "987-65-4321"
    And the user fills in Amount "2500"
    And the user clicks "Confirm Transfer"
    Then the self-healing agent detects the renamed button
    And the test completes successfully with a healed selector
