import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import Chatbot from './Chatbot';

const mockFetch = vi.fn();
global.fetch = mockFetch;

const mockSuccessResponse = {
  ok: true,
  json: async () => ({ response: 'test response', thread_id: 'test-thread-id' }),
};

describe('Chatbot', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  describe('API URL', () => {
    it('sends request to VITE_ATLAS_API_URL', async () => {
      mockFetch.mockResolvedValueOnce(mockSuccessResponse);

      render(<Chatbot />);

      // open chat window
      const toggleButton = screen.getByRole('button');
      fireEvent.click(toggleButton);

      // type and send message
      const textarea = screen.getByPlaceholderText('Type a message and press Enter...');
      fireEvent.change(textarea, { target: { value: 'hello' } });
      fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/atlas/chat'),
          expect.objectContaining({
            method: 'POST',
            headers: expect.objectContaining({
              'Content-Type': 'application/json',
            }),
          })
        );
      });
    });

    it('includes Bearer token in Authorization header', async () => {
      mockFetch.mockResolvedValueOnce(mockSuccessResponse);

      render(<Chatbot />);

      const toggleButton = screen.getByRole('button');
      fireEvent.click(toggleButton);

      const textarea = screen.getByPlaceholderText('Type a message and press Enter...');
      fireEvent.change(textarea, { target: { value: 'hello' } });
      fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.any(String),
          expect.objectContaining({
            headers: expect.objectContaining({
              'Authorization': expect.stringContaining('Bearer'),
            }),
          })
        );
      });
    });
  });

  describe('chat history', () => {
    // to be filled in by the chat history fix owner
    it.todo('preserves message history after toggling chat window');
    it.todo('preserves threadId after toggling chat window');
  });
});
