"""Tests for Retell envelope handling on check_vehicle_availability, get_test_drive_slots, and create_test_drive."""

from datetime import date, time, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas.business_tools import BookingRequest
from app.schemas.customer_tools import TestDriveSlotDiscoveryRequest
from app.schemas.inventory_tools import VehicleDetailsRequest

TOOL_HEADERS = {"X-Retell-Tool-Key": "test-retell-tool-key"}
FUTURE_DATE = (date.today() + timedelta(days=7)).isoformat()


# ---------------------------------------------------------------------------
# VehicleDetailsRequest — Schema Tests
# ---------------------------------------------------------------------------

class TestVehicleDetailsRequestSchema:
    """Schema-level validation for VehicleDetailsRequest."""

    def test_direct_json_accepted(self):
        req = VehicleDetailsRequest.model_validate({"vehicle_id": "VEH-000001"})
        assert req.vehicle_id == "VEH-000001"

    def test_retell_wrapper_check_vehicle_availability(self):
        req = VehicleDetailsRequest.model_validate({
            "call": {"call_id": "test"},
            "name": "check_vehicle_availability",
            "args": {"vehicle_id": "VEH-000001"},
        })
        assert req.vehicle_id == "VEH-000001"

    def test_retell_wrapper_get_vehicle_details(self):
        req = VehicleDetailsRequest.model_validate({
            "call": {"call_id": "test"},
            "name": "get_vehicle_details",
            "args": {"vehicle_id": "VEH-000001"},
        })
        assert req.vehicle_id == "VEH-000001"

    def test_invalid_vehicle_id_pattern(self):
        with pytest.raises(ValidationError):
            VehicleDetailsRequest.model_validate({"vehicle_id": "INVALID"})

    def test_args_without_name_rejected(self):
        with pytest.raises(ValidationError, match="'args' present without 'name'"):
            VehicleDetailsRequest.model_validate({
                "args": {"vehicle_id": "VEH-000001"},
            })

    def test_incorrect_function_name_rejected(self):
        with pytest.raises(ValidationError, match="Invalid function name"):
            VehicleDetailsRequest.model_validate({
                "call": {"call_id": "test"},
                "name": "wrong_function",
                "args": {"vehicle_id": "VEH-000001"},
            })

    def test_non_dict_args_rejected(self):
        with pytest.raises(ValidationError, match="Malformed Retell wrapper"):
            VehicleDetailsRequest.model_validate({
                "call": {"call_id": "test"},
                "name": "check_vehicle_availability",
                "args": "not-a-dict",
            })

    def test_call_and_name_without_args_rejected(self):
        with pytest.raises(ValidationError, match="missing 'args'"):
            VehicleDetailsRequest.model_validate({
                "call": {"call_id": "test"},
                "name": "check_vehicle_availability",
            })

    def test_name_only_rejected_as_ambiguous(self):
        with pytest.raises(ValidationError, match="Ambiguous payload"):
            VehicleDetailsRequest.model_validate({
                "name": "check_vehicle_availability",
            })

    def test_call_only_rejected_as_ambiguous(self):
        with pytest.raises(ValidationError, match="Ambiguous payload"):
            VehicleDetailsRequest.model_validate({
                "call": {"call_id": "test"},
            })

    def test_direct_fields_mixed_with_name_rejected(self):
        with pytest.raises(ValidationError, match="Ambiguous payload"):
            VehicleDetailsRequest.model_validate({
                "vehicle_id": "VEH-000001",
                "name": "check_vehicle_availability",
            })


# ---------------------------------------------------------------------------
# TestDriveSlotDiscoveryRequest — Schema Tests
# ---------------------------------------------------------------------------

class TestTestDriveSlotDiscoveryRequestSchema:
    """Schema-level validation for TestDriveSlotDiscoveryRequest."""

    def test_direct_json_accepted(self):
        req = TestDriveSlotDiscoveryRequest.model_validate({
            "vehicle_id": "VEH-000001",
            "requested_date": FUTURE_DATE,
        })
        assert req.vehicle_id == "VEH-000001"

    def test_direct_json_with_optional_fields(self):
        req = TestDriveSlotDiscoveryRequest.model_validate({
            "vehicle_id": "VEH-000001",
            "requested_date": FUTURE_DATE,
            "days": 3,
            "salesperson_id": "SP-001",
            "limit": 10,
        })
        assert req.vehicle_id == "VEH-000001"
        assert req.days == 3
        assert req.salesperson_id == "SP-001"
        assert req.limit == 10

    def test_retell_wrapper_accepted(self):
        req = TestDriveSlotDiscoveryRequest.model_validate({
            "call": {"call_id": "test"},
            "name": "get_test_drive_slots",
            "args": {
                "vehicle_id": "VEH-000001",
                "requested_date": FUTURE_DATE,
            },
        })
        assert req.vehicle_id == "VEH-000001"

    def test_retell_wrapper_with_optional_fields(self):
        req = TestDriveSlotDiscoveryRequest.model_validate({
            "call": {"call_id": "test"},
            "name": "get_test_drive_slots",
            "args": {
                "vehicle_id": "VEH-000001",
                "requested_date": FUTURE_DATE,
                "days": 5,
                "salesperson_id": "SP-002",
            },
        })
        assert req.days == 5
        assert req.salesperson_id == "SP-002"

    def test_args_without_name_rejected(self):
        with pytest.raises(ValidationError, match="'args' present without 'name'"):
            TestDriveSlotDiscoveryRequest.model_validate({
                "args": {"vehicle_id": "VEH-000001", "requested_date": FUTURE_DATE},
            })

    def test_incorrect_function_name_rejected(self):
        with pytest.raises(ValidationError, match="Invalid function name"):
            TestDriveSlotDiscoveryRequest.model_validate({
                "call": {"call_id": "test"},
                "name": "wrong_function",
                "args": {"vehicle_id": "VEH-000001", "requested_date": FUTURE_DATE},
            })

    def test_non_dict_args_rejected(self):
        with pytest.raises(ValidationError, match="Malformed Retell wrapper"):
            TestDriveSlotDiscoveryRequest.model_validate({
                "call": {"call_id": "test"},
                "name": "get_test_drive_slots",
                "args": 12345,
            })

    def test_call_and_name_without_args_rejected(self):
        with pytest.raises(ValidationError, match="missing 'args'"):
            TestDriveSlotDiscoveryRequest.model_validate({
                "call": {"call_id": "test"},
                "name": "get_test_drive_slots",
            })

    def test_ambiguous_name_only_rejected(self):
        with pytest.raises(ValidationError, match="Ambiguous payload"):
            TestDriveSlotDiscoveryRequest.model_validate({
                "name": "get_test_drive_slots",
            })

    def test_extra_fields_inside_args_forbidden(self):
        with pytest.raises(ValidationError):
            TestDriveSlotDiscoveryRequest.model_validate({
                "call": {"call_id": "test"},
                "name": "get_test_drive_slots",
                "args": {
                    "vehicle_id": "VEH-000001",
                    "requested_date": FUTURE_DATE,
                    "secret_field": "nope",
                },
            })

    def test_start_date_alias_accepted_in_wrapper(self):
        req = TestDriveSlotDiscoveryRequest.model_validate({
            "call": {"call_id": "test"},
            "name": "get_test_drive_slots",
            "args": {
                "vehicle_id": "VEH-000001",
                "start_date": FUTURE_DATE,
            },
        })
        assert req.vehicle_id == "VEH-000001"


# ---------------------------------------------------------------------------
# BookingRequest — Schema Tests
# ---------------------------------------------------------------------------

class TestBookingRequestSchema:
    """Schema-level validation for BookingRequest."""

    def _valid_args(self):
        return {
            "lead_id": "LEAD-004002",
            "customer_id": "CUST-005001",
            "vehicle_id": "VEH-000001",
            "salesperson_id": "SP-001",
            "appointment_date": FUTURE_DATE,
            "appointment_time": "10:00:00",
        }

    def test_direct_json_accepted(self):
        req = BookingRequest.model_validate(self._valid_args())
        assert req.lead_id == "LEAD-004002"
        assert req.customer_id == "CUST-005001"
        assert req.vehicle_id == "VEH-000001"
        assert req.salesperson_id == "SP-001"

    def test_retell_wrapper_accepted(self):
        req = BookingRequest.model_validate({
            "call": {"call_id": "test"},
            "name": "create_test_drive",
            "args": self._valid_args(),
        })
        assert req.lead_id == "LEAD-004002"
        assert req.vehicle_id == "VEH-000001"

    def test_retell_wrapper_with_notes(self):
        args = self._valid_args()
        args["notes"] = "Customer prefers morning slot"
        req = BookingRequest.model_validate({
            "call": {"call_id": "test"},
            "name": "create_test_drive",
            "args": args,
        })
        assert req.notes == "Customer prefers morning slot"

    def test_args_without_name_rejected(self):
        with pytest.raises(ValidationError, match="'args' present without 'name'"):
            BookingRequest.model_validate({"args": self._valid_args()})

    def test_incorrect_function_name_rejected(self):
        with pytest.raises(ValidationError, match="Invalid function name"):
            BookingRequest.model_validate({
                "call": {"call_id": "test"},
                "name": "create_or_update_lead",
                "args": self._valid_args(),
            })

    def test_non_dict_args_rejected(self):
        with pytest.raises(ValidationError, match="Malformed Retell wrapper"):
            BookingRequest.model_validate({
                "call": {"call_id": "test"},
                "name": "create_test_drive",
                "args": [1, 2, 3],
            })

    def test_call_and_name_without_args_rejected(self):
        with pytest.raises(ValidationError, match="missing 'args'"):
            BookingRequest.model_validate({
                "call": {"call_id": "test"},
                "name": "create_test_drive",
            })

    def test_ambiguous_call_only_rejected(self):
        with pytest.raises(ValidationError, match="Ambiguous payload"):
            BookingRequest.model_validate({"call": {"call_id": "test"}})

    def test_ambiguous_direct_mixed_with_name_rejected(self):
        args = self._valid_args()
        args["name"] = "create_test_drive"
        with pytest.raises(ValidationError, match="Ambiguous payload"):
            BookingRequest.model_validate(args)

    def test_extra_fields_inside_args_forbidden(self):
        args = self._valid_args()
        args["internal_score"] = 99
        with pytest.raises(ValidationError):
            BookingRequest.model_validate({
                "call": {"call_id": "test"},
                "name": "create_test_drive",
                "args": args,
            })

    def test_appointment_time_boundary_preserved_in_wrapper(self):
        args = self._valid_args()
        args["appointment_time"] = "10:15:00"
        with pytest.raises(ValidationError, match="30-minute boundary"):
            BookingRequest.model_validate({
                "call": {"call_id": "test"},
                "name": "create_test_drive",
                "args": args,
            })

    def test_missing_required_field_in_wrapper_rejected(self):
        args = self._valid_args()
        del args["lead_id"]
        with pytest.raises(ValidationError):
            BookingRequest.model_validate({
                "call": {"call_id": "test"},
                "name": "create_test_drive",
                "args": args,
            })


# ---------------------------------------------------------------------------
# Route Integration Tests — check-vehicle-availability POST
# ---------------------------------------------------------------------------

class TestCheckVehicleAvailabilityRoute:
    """FastAPI route tests for POST /api/tools/check-vehicle-availability."""

    def _mock_availability(self):
        from app.schemas.inventory_tools import VehicleAvailability
        return VehicleAvailability(
            vehicle_id="VEH-000001",
            vehicle_status="Available",
            test_drive_available=True,
            can_book_test_drive=True,
            reason="Vehicle is available for test drives",
        )

    def test_route_accepts_direct_json(self, monkeypatch):
        monkeypatch.setattr(
            "app.routes.inventory_tools.check_vehicle_availability",
            lambda vid, repo: self._mock_availability(),
        )
        app.dependency_overrides[
            __import__("app.routes.inventory_tools", fromlist=["get_inventory_repository"]).get_inventory_repository
        ] = lambda: MagicMock()
        try:
            response = TestClient(app, headers=TOOL_HEADERS).post(
                "/api/tools/check-vehicle-availability",
                json={"vehicle_id": "VEH-000001"},
            )
            assert response.status_code == 200
            assert response.json()["success"] is True
            assert response.json()["availability"]["vehicle_id"] == "VEH-000001"
        finally:
            app.dependency_overrides.clear()

    def test_route_accepts_retell_wrapper(self, monkeypatch):
        monkeypatch.setattr(
            "app.routes.inventory_tools.check_vehicle_availability",
            lambda vid, repo: self._mock_availability(),
        )
        app.dependency_overrides[
            __import__("app.routes.inventory_tools", fromlist=["get_inventory_repository"]).get_inventory_repository
        ] = lambda: MagicMock()
        try:
            response = TestClient(app, headers=TOOL_HEADERS).post(
                "/api/tools/check-vehicle-availability",
                json={
                    "call": {"call_id": "test"},
                    "name": "check_vehicle_availability",
                    "args": {"vehicle_id": "VEH-000001"},
                },
            )
            assert response.status_code == 200
            assert response.json()["availability"]["vehicle_id"] == "VEH-000001"
        finally:
            app.dependency_overrides.clear()

    def test_route_rejects_wrong_tool_name(self):
        app.dependency_overrides[
            __import__("app.routes.inventory_tools", fromlist=["get_inventory_repository"]).get_inventory_repository
        ] = lambda: MagicMock()
        try:
            response = TestClient(app, headers=TOOL_HEADERS).post(
                "/api/tools/check-vehicle-availability",
                json={
                    "call": {"call_id": "test"},
                    "name": "wrong_name",
                    "args": {"vehicle_id": "VEH-000001"},
                },
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Route Integration Tests — get-test-drive-slots POST
# ---------------------------------------------------------------------------

class TestGetTestDriveSlotsRoute:
    """FastAPI route tests for POST /api/tools/get-test-drive-slots."""

    def _mock_availability(self):
        from app.schemas.inventory_tools import VehicleAvailability
        return VehicleAvailability(
            vehicle_id="VEH-000001",
            vehicle_status="Available",
            test_drive_available=True,
            can_book_test_drive=True,
            reason="Vehicle is available",
        )

    def _mock_slots_response(self):
        from app.schemas.customer_tools import TestDriveSlotsResponse
        return TestDriveSlotsResponse(count=0, slots=[])

    def test_route_accepts_direct_json(self, monkeypatch):
        from app.routes.customer_tools import get_customer_tools_repository, get_test_drive_inventory_repository
        monkeypatch.setattr(
            "app.routes.customer_tools.check_vehicle_availability",
            lambda vid, repo: self._mock_availability(),
        )
        monkeypatch.setattr(
            "app.routes.customer_tools.get_test_drive_slots",
            lambda query, repo: self._mock_slots_response(),
        )
        app.dependency_overrides[get_customer_tools_repository] = lambda: MagicMock()
        app.dependency_overrides[get_test_drive_inventory_repository] = lambda: MagicMock()
        try:
            response = TestClient(app, headers=TOOL_HEADERS).post(
                "/api/tools/get-test-drive-slots",
                json={
                    "vehicle_id": "VEH-000001",
                    "requested_date": FUTURE_DATE,
                },
            )
            assert response.status_code == 200
            assert response.json()["success"] is True
        finally:
            app.dependency_overrides.clear()

    def test_route_accepts_retell_wrapper(self, monkeypatch):
        from app.routes.customer_tools import get_customer_tools_repository, get_test_drive_inventory_repository
        monkeypatch.setattr(
            "app.routes.customer_tools.check_vehicle_availability",
            lambda vid, repo: self._mock_availability(),
        )
        monkeypatch.setattr(
            "app.routes.customer_tools.get_test_drive_slots",
            lambda query, repo: self._mock_slots_response(),
        )
        app.dependency_overrides[get_customer_tools_repository] = lambda: MagicMock()
        app.dependency_overrides[get_test_drive_inventory_repository] = lambda: MagicMock()
        try:
            response = TestClient(app, headers=TOOL_HEADERS).post(
                "/api/tools/get-test-drive-slots",
                json={
                    "call": {"call_id": "test"},
                    "name": "get_test_drive_slots",
                    "args": {
                        "vehicle_id": "VEH-000001",
                        "requested_date": FUTURE_DATE,
                    },
                },
            )
            assert response.status_code == 200
            assert response.json()["success"] is True
        finally:
            app.dependency_overrides.clear()

    def test_route_rejects_wrong_tool_name(self):
        from app.routes.customer_tools import get_customer_tools_repository, get_test_drive_inventory_repository
        app.dependency_overrides[get_customer_tools_repository] = lambda: MagicMock()
        app.dependency_overrides[get_test_drive_inventory_repository] = lambda: MagicMock()
        try:
            response = TestClient(app, headers=TOOL_HEADERS).post(
                "/api/tools/get-test-drive-slots",
                json={
                    "call": {"call_id": "test"},
                    "name": "wrong_function",
                    "args": {
                        "vehicle_id": "VEH-000001",
                        "requested_date": FUTURE_DATE,
                    },
                },
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Route Integration Tests — create-test-drive POST
# ---------------------------------------------------------------------------

class TestCreateTestDriveRoute:
    """FastAPI route tests for POST /api/tools/create-test-drive."""

    def _valid_args(self):
        return {
            "lead_id": "LEAD-004002",
            "customer_id": "CUST-005001",
            "vehicle_id": "VEH-000001",
            "salesperson_id": "SP-001",
            "appointment_date": FUTURE_DATE,
            "appointment_time": "10:00:00",
        }

    def _mock_booking_response(self):
        from app.schemas.business_tools import BookingResponse
        return BookingResponse(
            created=True,
            appointment={
                "appointment_id": "APT-001504",
                "lead_id": "LEAD-004002",
                "vehicle_id": "VEH-000001",
                "status": "Confirmed",
            },
        )

    def test_route_accepts_direct_json(self, monkeypatch):
        from app.routes.business_tools import get_business_client
        monkeypatch.setattr(
            "app.routes.business_tools.create_test_drive",
            lambda req, client: self._mock_booking_response(),
        )
        app.dependency_overrides[get_business_client] = lambda: MagicMock()
        try:
            response = TestClient(app, headers=TOOL_HEADERS).post(
                "/api/tools/create-test-drive",
                json=self._valid_args(),
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["created"] is True
            assert data["appointment"]["appointment_id"] == "APT-001504"
        finally:
            app.dependency_overrides.clear()

    def test_route_accepts_retell_wrapper(self, monkeypatch):
        from app.routes.business_tools import get_business_client
        captured = []
        def mock_service(req, client):
            captured.append(req)
            return self._mock_booking_response()
        monkeypatch.setattr(
            "app.routes.business_tools.create_test_drive",
            mock_service,
        )
        app.dependency_overrides[get_business_client] = lambda: MagicMock()
        try:
            response = TestClient(app, headers=TOOL_HEADERS).post(
                "/api/tools/create-test-drive",
                json={
                    "call": {"call_id": "test"},
                    "name": "create_test_drive",
                    "args": self._valid_args(),
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(captured) == 1
            assert captured[0].lead_id == "LEAD-004002"
            assert captured[0].vehicle_id == "VEH-000001"
        finally:
            app.dependency_overrides.clear()

    def test_route_rejects_wrong_tool_name(self):
        from app.routes.business_tools import get_business_client
        app.dependency_overrides[get_business_client] = lambda: MagicMock()
        try:
            response = TestClient(app, headers=TOOL_HEADERS).post(
                "/api/tools/create-test-drive",
                json={
                    "call": {"call_id": "test"},
                    "name": "create_or_update_lead",
                    "args": self._valid_args(),
                },
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()
