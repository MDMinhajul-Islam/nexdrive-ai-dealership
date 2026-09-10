# Vehicle image storage rollout

Vehicle photos are public dealership marketing assets stored in the public
Supabase Storage bucket `vehicle-images`. PostgreSQL stores metadata only.

## Existing local assets

The files below are generic body-type illustrations, not photographs of a
specific inventory record. They remain frontend fallbacks and must **not** be
inserted into `public.vehicle_images` as verified vehicle photos:

- `frontend/public/images/vehicle-convertible.png`
- `frontend/public/images/vehicle-coupe.png`
- `frontend/public/images/vehicle-ev.png` (currently unused)
- `frontend/public/images/vehicle-hatchback.png`
- `frontend/public/images/vehicle-minivan.png`
- `frontend/public/images/vehicle-sedan.png`
- `frontend/public/images/vehicle-suv.png`
- `frontend/public/images/vehicle-truck.png`
- `frontend/public/images/vehicle-van.png`
- `frontend/public/images/vehicle-wagon.png`

`frontend/public/images/nexdrive-hero.png` is site artwork and is unrelated to
inventory images.

## Upload and metadata workflow

1. Apply `database/schema/13_vehicle_storage_images.sql`.
2. Create a public Storage bucket named `vehicle-images`. Restrict uploads to
   image MIME types and dealership administrators; public access is read-only.
3. Upload actual photos for each vehicle using paths such as:
   - `vehicles/VEH-000001/front.webp`
   - `vehicles/VEH-000001/rear.webp`
   - `vehicles/VEH-000001/interior.webp`
4. Only after each object exists, insert its metadata:

```sql
INSERT INTO public.vehicle_images
    (vehicle_id, storage_path, sort_order, is_primary)
VALUES
    ('VEH-000001', 'vehicles/VEH-000001/front.webp', 0, true),
    ('VEH-000001', 'vehicles/VEH-000001/rear.webp', 1, false),
    ('VEH-000001', 'vehicles/VEH-000001/interior.webp', 2, false);
```

Replace the example ID and paths with the actual uploaded vehicle. The schema
allows only one primary image and one row at each sort position per vehicle.
Do not create a metadata row before its corresponding Storage object exists.

Migration 11's licensed make/model URL cache is preserved as
`public.vehicle_model_images`; it is not treated as verified per-vehicle
photography.
