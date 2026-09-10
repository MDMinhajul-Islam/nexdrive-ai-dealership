import { useMemo, useState } from 'react';

const bodyTypeImages={SUV:'/images/vehicle-suv.png',Sedan:'/images/vehicle-sedan.png',Truck:'/images/vehicle-truck.png',Hatchback:'/images/vehicle-hatchback.png',Coupe:'/images/vehicle-coupe.png',Wagon:'/images/vehicle-wagon.png',Minivan:'/images/vehicle-minivan.png',Van:'/images/vehicle-van.png',Convertible:'/images/vehicle-convertible.png'};

export const fallbackVehicleImage=vehicle=>bodyTypeImages[vehicle?.body_type]||bodyTypeImages.Sedan;

export function orderedVehicleImages(vehicle){
  const images=Array.isArray(vehicle?.images)?vehicle.images.filter(image=>image&&typeof image.url==='string'&&image.url):[];
  return [...images].sort((left,right)=>Number(Boolean(right.is_primary))-Number(Boolean(left.is_primary))||Number(left.sort_order||0)-Number(right.sort_order||0));
}

export function primaryVehicleImage(vehicle){
  return vehicle?.primary_image_url||orderedVehicleImages(vehicle)[0]?.url||vehicle?.image_url||vehicle?.image_thumbnail_url||null;
}

export function VehiclePhoto({vehicle,imageUrl=null,labelClass='vehicle-photo-fallback',alt=''}){
  const verifiedUrl=imageUrl||primaryVehicleImage(vehicle);
  const [failedUrl,setFailedUrl]=useState(null);
  const hasVerifiedImage=Boolean(verifiedUrl)&&failedUrl!==verifiedUrl;
  return <>
    <img src={hasVerifiedImage?verifiedUrl:fallbackVehicleImage(vehicle)} onError={()=>setFailedUrl(verifiedUrl)} alt={hasVerifiedImage?alt:`Vehicle photo unavailable${vehicle?.vehicle_id?` for ${vehicle.vehicle_id}`:''}`}/>
    {!hasVerifiedImage&&<small className={labelClass}>Illustrative placeholder · no verified photo</small>}
  </>;
}

export function VehicleGallery({vehicle}){
  const images=useMemo(()=>orderedVehicleImages(vehicle),[vehicle]);
  const initialUrl=images[0]?.url||primaryVehicleImage(vehicle);
  const [requestedUrl,setRequestedUrl]=useState(null);
  const selectedUrl=images.some(image=>image.url===requestedUrl)?requestedUrl:initialUrl;
  const alt=`${vehicle.year} ${vehicle.make} ${vehicle.model}`;
  return <>
    <VehiclePhoto vehicle={vehicle} imageUrl={selectedUrl} labelClass="representative-detail" alt={alt}/>
    {images.length>1&&<div className="vehicle-gallery-thumbnails" aria-label="Vehicle images">
      {images.map((image,index)=><button type="button" className={image.url===selectedUrl?'active':''} key={`${image.url}-${image.sort_order}`} onClick={()=>setRequestedUrl(image.url)} aria-label={`Show vehicle image ${index+1}`}><img src={image.url} alt="" onError={event=>{event.currentTarget.hidden=true}}/></button>)}
    </div>}
  </>;
}
