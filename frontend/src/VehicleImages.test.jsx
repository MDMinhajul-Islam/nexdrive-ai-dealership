// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { VehicleGallery, VehiclePhoto } from './VehicleImages';

const vehicle={vehicle_id:'VEH-000001',year:2026,make:'Toyota',model:'RAV4',body_type:'SUV'};

afterEach(cleanup);

describe('vehicle listing image',()=>{
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
