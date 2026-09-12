// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  api: vi.fn(),
  clearSession: vi.fn(),
  getSession: vi.fn(),
}));

vi.mock('./api', () => mocks);

import { AdminDashboard } from './AdminDashboard';

const summary = {
  vehicles: 10,
  available_vehicles: 7,
  leads: 4,
  appointments: 3,
  customers: 8,
  confirmed_appointments: 2,
  hot_leads: 1,
};

beforeEach(() => {
  mocks.api.mockReset();
  mocks.clearSession.mockReset();
  mocks.getSession.mockReturnValue({ user: { email: 'admin@nexdrive.demo' } });
});
afterEach(cleanup);

describe('admin dashboard', () => {
  it('retains the modal and row until deletion is confirmed by the backend', async () => {
    let resolveDelete;
    mocks.api.mockResolvedValueOnce(summary)
      .mockResolvedValueOnce({ records: [{ appointment_id: 'APT-000321', status: 'Confirmed' }] })
      .mockReturnValueOnce(new Promise(resolve => { resolveDelete = resolve; }));
    render(<AdminDashboard />);
    await screen.findByText('Available inventory');
    fireEvent.click(screen.getByRole('button', { name: 'Bookings' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Delete' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByRole('cell', { name: 'APT-000321' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Deleting…' })).toBeDisabled();
    await act(async () => resolveDelete({ success: true }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.queryByRole('cell', { name: 'APT-000321' })).not.toBeInTheDocument();
  });
  it('renders real overview values after its loading state', async () => {
    let resolveSummary;
    mocks.api.mockReturnValueOnce(new Promise(resolve => { resolveSummary = resolve; }));
    render(<AdminDashboard />);

    expect(screen.getByRole('status')).toHaveTextContent('Loading live operations data');
    resolveSummary(summary);

    await waitFor(() => expect(screen.getByText('Available inventory')).toBeInTheDocument());
    expect(screen.getByText('7')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Bookings' })).toBeInTheDocument();
  });

  it('shows a recoverable overview error', async () => {
    mocks.api.mockRejectedValueOnce(new Error('Dashboard summary unavailable'));
    render(<AdminDashboard />);

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Dashboard data is unavailable'));
    expect(screen.getByText('Dashboard summary unavailable')).toBeInTheDocument();
  });

  it('renders an empty workspace without inventing records', async () => {
    mocks.api
      .mockResolvedValueOnce(summary)
      .mockResolvedValueOnce({ records: [] });
    render(<AdminDashboard />);

    await waitFor(() => expect(screen.getByText('Available inventory')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Bookings' }));
    await waitFor(() => expect(screen.getByText('No records found')).toBeInTheDocument());
  });

  it('approves a requested booking and removes a booking only after confirmation', async () => {
    mocks.api
      .mockResolvedValueOnce(summary)
      .mockResolvedValueOnce({ records: [{ appointment_id: 'APT-000001', customer_id: 'CUST-000001', vehicle_id: 'VEH-000001', salesperson_id: 'SP-001', appointment_date: '2026-09-15', appointment_time: '14:30:00', status: 'Requested' }] })
      .mockResolvedValueOnce({ booking: { appointment_id: 'APT-000001', customer_id: 'CUST-000001', vehicle_id: 'VEH-000001', salesperson_id: 'SP-001', appointment_date: '2026-09-15', appointment_time: '14:30:00', status: 'Confirmed' }, message: 'Booking approved' })
      .mockResolvedValueOnce({ success: true });
    render(<AdminDashboard />);

    await waitFor(() => expect(screen.getByText('Available inventory')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Bookings' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Approve' })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument());
    expect(screen.getByText('Confirmed')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(screen.getByRole('dialog')).toHaveTextContent('Delete this booking?');
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(screen.queryByText('APT-000001')).not.toBeInTheDocument());
    expect(mocks.api).toHaveBeenCalledWith('/api/admin/appointments/APT-000001', { method: 'DELETE' }, true);
  });

  it('rejects a requested booking and displays a safe API failure', async () => {
    const booking = { appointment_id: 'APT-000002', customer_id: 'CUST-000002', vehicle_id: 'VEH-000002', salesperson_id: 'SP-002', appointment_date: '2026-09-16', appointment_time: '10:00:00', status: 'Requested' };
    mocks.api
      .mockResolvedValueOnce(summary)
      .mockResolvedValueOnce({ records: [booking] })
      .mockResolvedValueOnce({ booking: { ...booking, status: 'Cancelled' }, message: 'Booking rejected' });
    render(<AdminDashboard />);

    await waitFor(() => expect(screen.getByText('Available inventory')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Bookings' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Reject' })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Reject' }));
    await waitFor(() => expect(screen.getByText('Cancelled')).toBeInTheDocument());
    expect(screen.queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument();

    mocks.api.mockRejectedValueOnce(new Error('Booking deletion unavailable'));
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Booking deletion unavailable'));
    expect(screen.getAllByText('APT-000002')).not.toHaveLength(0);
  });
});
