// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { VehicleGallery, VehiclePhoto } from './VehicleImages';

const vehicle={vehicle_id:'VEH-000001',year:2026,make:'Toyota',model:'RAV4',body_type:'SUV'};

afterEach(cleanup);

describe('vehicle listing image',()=>{
  it('keeps model photos associated with vehicles after filtering and rerendering',()=>{
    const camry={...vehicle,model:'Camry',image_url:'https://photos.example/camry.jpg',image_is_representative:true};
    const rav4={...vehicle,vehicle_id:'VEH-000002',image_url:'https://photos.example/rav4.jpg',image_is_representative:true};
    const {rerender}=render(<VehiclePhoto vehicle={camry} alt="Toyota Camry"/>);
    expect(screen.getByRole('img')).toHaveAttribute('src',camry.image_url);
    fireEvent.error(screen.getByRole('img'));
    rerender(<VehiclePhoto vehicle={rav4} alt="Toyota RAV4"/>);
    expect(screen.getByRole('img')).toHaveAttribute('src',rav4.image_url);
    rerender(<VehicleGallery vehicle={rav4}/>);
    expect(screen.getByRole('img')).toHaveAttribute('src',rav4.image_url);
  });
  it('renders the backend primary image',()=>{
    render(<VehiclePhoto vehicle={{...vehicle,primary_image_url:'https://project.supabase.co/storage/front.webp'}} alt="Toyota RAV4"/>);

    expect(screen.getByRole('img')).toHaveAttribute('src','https://project.supabase.co/storage/front.webp');
    expect(screen.queryByText(/Illustrative placeholder/)).not.toBeInTheDocument();
  });

  it('labels the generic fallback when no verified image exists',()=>{
    render(<VehiclePhoto vehicle={vehicle}/>);

    expect(screen.getByRole('img').getAttribute('src')).toContain('/images/vehicle-suv.png');
    expect(screen.getByText('Illustrative placeholder · no verified photo')).toBeInTheDocument();
  });

  it('uses the labeled fallback when a storage object cannot load',()=>{
    render(<VehiclePhoto vehicle={{...vehicle,primary_image_url:'https://project.supabase.co/storage/missing.webp'}} alt="Toyota RAV4"/>);
    fireEvent.error(screen.getByRole('img'));

    expect(screen.getByRole('img').getAttribute('src')).toContain('/images/vehicle-suv.png');
    expect(screen.getByText('Illustrative placeholder · no verified photo')).toBeInTheDocument();
  });
});

describe('vehicle detail gallery',()=>{
  it('orders primary first and lets the customer select another image',()=>{
    render(<VehicleGallery vehicle={{...vehicle,images:[
      {url:'https://project.supabase.co/storage/rear.webp',is_primary:false,sort_order:1},
      {url:'https://project.supabase.co/storage/front.webp',is_primary:true,sort_order:0},
      {url:'https://project.supabase.co/storage/interior.webp',is_primary:false,sort_order:2},
    ]}}/>);

    const mainImage=screen.getByRole('img',{name:'2026 Toyota RAV4'});
    expect(mainImage).toHaveAttribute('src','https://project.supabase.co/storage/front.webp');
    fireEvent.click(screen.getByRole('button',{name:'Show vehicle image 2'}));
    expect(mainImage).toHaveAttribute('src','https://project.supabase.co/storage/rear.webp');
  });
});
