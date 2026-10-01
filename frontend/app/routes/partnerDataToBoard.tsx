import React, { useState } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';

const ATLAS_API_URL = import.meta.env.VITE_ATLAS_API_URL;

export default function FileUploader() {
  const [file, setFile] = useState(null);
  const [workspaceName, setWorkspaceName] = useState('');
  const [boardName, setBoardName] = useState('');
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [controller, setController] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file || !workspaceName || !boardName) {
      alert('Please fill all fields and select a file.');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('workspace_name', workspaceName);
    formData.append('board_name', boardName);

    const abortController = new AbortController();
    setController(abortController);
    setLoading(true);
    setResponse(null);

    try {
      const res = await axios.post(`${ATLAS_API_URL}/mondayboard/populate`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        signal: abortController.signal,
      });
      setResponse(res.data);
    } catch (err) {
      if (err.name === 'CanceledError') {
        setResponse('Upload canceled');
      } else {
        setResponse(err.response?.data || 'Error occurred');
      }
    } finally {
      setLoading(false);
      setController(null);
    }
  };

  const handleCancel = () => {
    if (controller) controller.abort();
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-md bg-white p-6 rounded-2xl shadow-md">
        <h1 className="text-2xl font-semibold mb-4 text-center">Automatically create pre-cap board from partner startup data</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="text"
            placeholder="Workspace Name"
            value={workspaceName}
            onChange={(e) => setWorkspaceName(e.target.value)}
            className="w-full p-2 border rounded"
          />

          <input
            type="text"
            placeholder="Board Name"
            value={boardName}
            onChange={(e) => setBoardName(e.target.value)}
            className="w-full p-2 border rounded"
          />

          <input
            type="file"
            accept=".csv"
            onChange={(e) => setFile(e.target.files[0])}
            className="border border-gray-300 rounded-md p-2 cursor-pointer focus:outline-none focus:ring-2 focus:ring-blue-500"
          />

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 transition disabled:opacity-50"
          >
            {loading ? 'Uploading...' : 'Submit'}
          </button>

          {loading && (
            <button
              type="button"
              onClick={handleCancel}
              className="w-full bg-red-500 text-white py-2 rounded hover:bg-red-600 transition"
            >
              Cancel Upload
            </button>
          )}
        </form>

        {loading && (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 1, ease: 'linear' }}
            className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mt-4"
          />
        )}

        {response && (
          <div className="mt-4 p-3 bg-gray-100 rounded text-sm">
            <pre>{JSON.stringify(response, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  );
}