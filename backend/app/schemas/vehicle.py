"""Vehicle API schemas."""

from pydantic import BaseModel, Field


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


class VehicleDetailsResponse(BaseModel):
    success: bool = True
    vehicle: VehicleDetails
