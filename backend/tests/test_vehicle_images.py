from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.routes.inventory_tools import get_inventory_repository
from app.schemas.inventory_tools import InventorySearchFilters
from app.services import vehicle_images as image_service
from app.services.inventory_tools import get_vehicle_details, search_inventory
from app.services.vehicle_images import attach_vehicle_images


class ImageQuery:
    def __init__(self, rows=None, error: Exception | None = None):
        self.rows = rows or []
        self.error = error
        self.vehicle_ids = []
        self.ordering = []

    def select(self, _columns):
        return self

    def in_(self, _column, values):
        self.vehicle_ids = values
        return self

    def order(self, column, **options):
        self.ordering.append((column, options))
        return self

    def range(self, _start, _end):
        return self

    def execute(self):
        if self.error:
            raise self.error
        return SimpleNamespace(data=self.rows)


class ImageDatabase:
    def __init__(self, rows=None, error: Exception | None = None):
        self.query = ImageQuery(rows, error)

    def table(self, name):
        assert name == "vehicle_images"
        return self.query


class ModelImageDatabase:
    def __init__(self, models, storage=None, storage_error=None):
        self.models = ImageQuery(models)
        self.storage = ImageQuery(storage, storage_error)

    def table(self, name):
        return self.storage if name == "vehicle_images" else self.models


def test_carsxe_fallback_matches_year_make_model_without_cross_vehicle_leakage(monkeypatch):
    _configure_url(monkeypatch)
    vehicles = [
        {"vehicle_id": "VEH-000001", "stock_number": "NX-000001", "year": 2024, "make": "Toyota", "model": "Camry"},
        {"vehicle_id": "VEH-000002", "year": 2024, "make": "Toyota", "model": "RAV4"},
        {"vehicle_id": "VEH-000003", "year": 2024, "make": "BMW", "model": "X5"},
        {"vehicle_id": "VEH-000004", "year": 2024, "make": "Ford", "model": "Mustang"},
        {"vehicle_id": "VEH-000005", "year": 2024, "make": "Tesla", "model": "Model 3"},
        {"vehicle_id": "VEH-000006", "year": 2025, "make": "Toyota", "model": "Camry"},
        {"vehicle_id": "VEH-000007", "year": 2024, "make": "BMW", "model": "Unknown"},
    ]
    models = [{"make": v["make"], "model": v["model"], "model_year": 2024,
               "image_url": f"https://photos.example/{v['vehicle_id']}.jpg", "provider": "CarsXE"}
              for v in vehicles[:5]]
    models.append({"make": "Toyota", "model": "Camry", "model_year": None,
                   "image_url": "https://photos.example/camry.jpg", "provider": "CarsXE"})
    db = ModelImageDatabase(models)
    result = attach_vehicle_images(db, vehicles)
    assert len({v["image_url"] for v in result[:5]}) == 5
    assert result[5]["image_url"] == "https://photos.example/camry.jpg"
    assert result[6]["image_url"] is None
    assert result[0]["stock_number"] == "NX-000001"
    expected = {v["vehicle_id"]: v["image_url"] for v in result}
    assert {v["vehicle_id"]: v["image_url"] for v in attach_vehicle_images(db, list(reversed(result)))} == expected
    assert attach_vehicle_images(db, [result[0]])[0]["image_url"] == expected["VEH-000001"]


def test_storage_has_priority_but_carsxe_survives_storage_rollout_failure(monkeypatch):
    _configure_url(monkeypatch)
    vehicle = {"vehicle_id": "VEH-000001", "make": "Toyota", "model": "Camry", "year": 2024}
    models = [{"make": "Toyota", "model": "Camry", "model_year": None,
               "image_url": "https://photos.example/camry.jpg", "provider": "CarsXE"}]
    storage = [{"id": 1, "vehicle_id": "VEH-000001", "storage_path": "vehicles/VEH-000001/front.webp",
                "sort_order": 0, "is_primary": True}]
    assert "/storage/" in attach_vehicle_images(ModelImageDatabase(models, storage), [dict(vehicle)])[0]["image_url"]
    assert attach_vehicle_images(ModelImageDatabase(models, storage_error=RuntimeError()), [dict(vehicle)])[0]["image_is_representative"] is True


def _configure_url(monkeypatch):
    monkeypatch.setattr(
        image_service,
        "get_settings",
        lambda: SimpleNamespace(supabase_url="https://project.supabase.co"),
    )


def test_vehicle_with_one_storage_image(monkeypatch):
    _configure_url(monkeypatch)
    vehicle = {"vehicle_id": "VEH-000001"}
    db = ImageDatabase([{
        "id": 1,
        "vehicle_id": "VEH-000001",
        "storage_path": "vehicles/VEH-000001/front.webp",
        "sort_order": 0,
        "is_primary": True,
    }])

    result = attach_vehicle_images(db, [vehicle])[0]

    expected_url = (
        "https://project.supabase.co/storage/v1/object/public/vehicle-images/"
        "vehicles/VEH-000001/front.webp"
    )
    assert result["primary_image_url"] == expected_url
    assert result["image_url"] == expected_url
    assert result["image_thumbnail_url"] == expected_url
    assert result["images"] == [{
        "url": expected_url,
        "is_primary": True,
        "sort_order": 0,
    }]
    assert db.query.vehicle_ids == ["VEH-000001"]


def test_vehicle_images_are_primary_first_then_sort_order(monkeypatch):
    _configure_url(monkeypatch)
    db = ImageDatabase([
        {"id": 3, "vehicle_id": "VEH-000001", "storage_path": "vehicles/VEH-000001/interior.webp", "sort_order": 2, "is_primary": False},
        {"id": 2, "vehicle_id": "VEH-000001", "storage_path": "vehicles/VEH-000001/rear.webp", "sort_order": 1, "is_primary": False},
        {"id": 1, "vehicle_id": "VEH-000001", "storage_path": "vehicles/VEH-000001/front.webp", "sort_order": 0, "is_primary": True},
    ])

    result = attach_vehicle_images(db, [{"vehicle_id": "VEH-000001"}])[0]

    assert [image["url"].rsplit("/", 1)[-1] for image in result["images"]] == [
        "front.webp",
        "rear.webp",
        "interior.webp",
    ]
    assert result["images"][0]["is_primary"] is True


def test_vehicle_with_no_image_has_stable_empty_fields(monkeypatch):
    _configure_url(monkeypatch)
    result = attach_vehicle_images(
        ImageDatabase([]), [{"vehicle_id": "VEH-000001"}]
    )[0]

    assert result["primary_image_url"] is None
    assert result["images"] == []
    assert result["image_url"] is None
    assert result["image_thumbnail_url"] is None
    assert result["image_is_representative"] is False


def test_invalid_path_and_metadata_failure_do_not_fabricate_images(monkeypatch):
    _configure_url(monkeypatch)
    invalid = attach_vehicle_images(
        ImageDatabase([{
            "id": 1,
            "vehicle_id": "VEH-000001",
            "storage_path": "vehicles/VEH-999999/front.webp",
            "sort_order": 0,
            "is_primary": True,
        }]),
        [{"vehicle_id": "VEH-000001"}],
    )[0]
    unavailable = attach_vehicle_images(
        ImageDatabase(error=RuntimeError("private provider detail")),
        [{"vehicle_id": "VEH-000001"}],
    )[0]

    assert invalid["primary_image_url"] is None
    assert invalid["images"] == []
    assert unavailable["primary_image_url"] is None
    assert unavailable["images"] == []


class StaticImageRepository:
    def __init__(self, row):
        self.row = row

    def search(self, _filters):
        return [self.row]

    def get(self, _vehicle_id):
        return self.row


def _inventory_row():
    image = {
        "url": "https://project.supabase.co/storage/v1/object/public/vehicle-images/vehicles/VEH-000001/front.webp",
        "is_primary": True,
        "sort_order": 0,
    }
    return {
        "vehicle_id": "VEH-000001",
        "vin": "NXD2LW9SL100W5WKZ",
        "stock_number": "NX-000001",
        "make": "Toyota",
        "model": "Camry",
        "year": 2024,
        "trim": "XLE",
        "body_type": "Sedan",
        "condition": "Used",
        "mileage": 26560,
        "exterior_color": "Silver Metallic",
        "interior_color": "Parchment Leather",
        "fuel_type": "Hybrid",
        "transmission": "Automatic",
        "drivetrain": "FWD",
        "seating_capacity": 5,
        "msrp": 37050,
        "sale_price": 28100,
        "vehicle_status": "Available",
        "test_drive_available": True,
        "warranty": "90-Day Dealer Limited Warranty",
        "certification": "None",
        "dealership_location": "Dallas Central",
        "features": ["Hybrid Powertrain"],
        "primary_image_url": image["url"],
        "images": [image],
        "image_url": image["url"],
        "image_thumbnail_url": image["url"],
    }


def test_inventory_search_and_details_return_image_contract():
    row = _inventory_row()
    repository = StaticImageRepository(row)

    search = search_inventory(
        InventorySearchFilters(make="Toyota"), repository
    ).model_dump()
    details = get_vehicle_details("VEH-000001", repository).model_dump()

    assert search["vehicles"][0]["primary_image_url"] == row["primary_image_url"]
    assert search["vehicles"][0]["images"] == row["images"]
    assert details["primary_image_url"] == row["primary_image_url"]
    assert details["images"] == row["images"]


def test_inventory_tool_endpoints_return_image_contract():
    row = _inventory_row()
    app.dependency_overrides[get_inventory_repository] = lambda: StaticImageRepository(row)
    client = TestClient(
        app, headers={"X-Retell-Tool-Key": "test-retell-tool-key"}
    )
    try:
        search_response = client.post(
            "/api/tools/search-inventory", json={"make": "Toyota"}
        )
        detail_response = client.get(
            "/api/tools/get-vehicle-details/VEH-000001"
        )
    finally:
        app.dependency_overrides.clear()

    assert search_response.status_code == 200
    assert detail_response.status_code == 200
    assert "primary_image_url" not in search_response.json()["vehicles"][0]
    assert "images" not in search_response.json()["vehicles"][0]
    assert "images" not in detail_response.json()["vehicle"]
