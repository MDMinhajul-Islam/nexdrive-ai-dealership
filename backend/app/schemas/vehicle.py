"""Vehicle API schemas."""

from pydantic import BaseModel, Field


class VehicleImage(BaseModel):
    url: str
    is_primary: bool
    sort_order: int


class VehicleDetails(BaseModel):
    vehicle_id: str
    vin: str
    stock_number: str
    make: str
    model: str
    year: int
    trim: str
    body_type: str
    condition: str
    mileage: int
    exterior_color: str
    interior_color: str
    fuel_type: str
    transmission: str
    drivetrain: str
    seating_capacity: int
    msrp: float
    sale_price: float
    vehicle_status: str
    test_drive_available: bool
    warranty: str
    certification: str
    dealership_location: str
    features: list[str] = Field(default_factory=list)
    primary_image_url: str | None = None
    images: list[VehicleImage] = Field(default_factory=list)
    # Backward-compatible image aliases used by older public clients.
    image_url: str | None = None
    image_thumbnail_url: str | None = None
    image_source_url: str | None = None
    image_license: str | None = None
    image_provider: str | None = None
    image_is_representative: bool = False


class VehicleDetailsResponse(BaseModel):
    success: bool = True
    vehicle: VehicleDetails
