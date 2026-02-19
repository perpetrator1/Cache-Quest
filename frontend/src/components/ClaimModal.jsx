import { useState, useEffect } from 'react';
import { Html5Qrcode } from 'html5-qrcode';
import axiosInstance from '../utils/axiosInstance';

export function ClaimModal({ spot, isOpen, onClose, onSuccess }) {
  const [activeTab, setActiveTab] = useState('code'); // 'code' or 'qr'
  const [code, setCode] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const scannerRef = useState(null)[0]; // Keep scanner instance

  // Handle code submission
  const handleSubmitCode = async (codeValue) => {
    if (!codeValue || isSubmitting) return;

    setIsSubmitting(true);
    setError('');

    try {
      const response = await axiosInstance.post('/api/spots/claim/', {
        code: codeValue.trim(),
      });

      // Success!
      if (onSuccess) {
        onSuccess(response.data);
      }
      
      // Close modal
      onClose();
    } catch (err) {
      console.error('Error claiming cache:', err);
      const errorMessage = err.response?.data?.error || err.response?.data?.message || 'Failed to claim cache. Please check the code and try again.';
      setError(errorMessage);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Handle manual code form submission
  const handleFormSubmit = (e) => {
    e.preventDefault();
    handleSubmitCode(code);
  };

  // Start QR scanner
  const startScanner = async () => {
    try {
      setIsScanning(true);
      setError('');

      const scanner = new Html5Qrcode('qr-reader');
      
      await scanner.start(
        { facingMode: 'environment' }, // Use back camera
        {
          fps: 10,
          qrbox: { width: 250, height: 250 },
        },
        (decodedText) => {
          // Auto-submit on successful scan
          console.log('QR Code scanned:', decodedText);
          scanner.stop().then(() => {
            setIsScanning(false);
            handleSubmitCode(decodedText);
          });
        },
        (errorMessage) => {
          // Scanning errors (usually just "no QR code found")
          // We can ignore these
        }
      );

      // Store scanner reference for cleanup
      scannerRef.current = scanner;
    } catch (err) {
      console.error('Error starting scanner:', err);
      setError('Failed to start camera. Please check permissions.');
      setIsScanning(false);
    }
  };

  // Stop QR scanner
  const stopScanner = async () => {
    if (scannerRef.current && isScanning) {
      try {
        await scannerRef.current.stop();
        scannerRef.current = null;
      } catch (err) {
        console.error('Error stopping scanner:', err);
      }
      setIsScanning(false);
    }
  };

  // Handle tab change
  useEffect(() => {
    if (activeTab === 'qr' && isOpen) {
      startScanner();
    } else {
      stopScanner();
    }

    return () => {
      stopScanner();
    };
  }, [activeTab, isOpen]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopScanner();
    };
  }, []);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setCode('');
      setError('');
      setActiveTab('code');
      stopScanner();
    }
  }, [isOpen]);

  if (!isOpen || !spot) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-lg shadow-2xl max-w-md w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">Claim Cache</h2>
          <button
            onClick={onClose}
            className="p-2 text-gray-500 hover:text-gray-700 rounded-full hover:bg-gray-100 transition"
            style={{ minWidth: '40px', minHeight: '40px' }}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Spot name */}
        <div className="px-6 py-3 bg-gray-50 border-b border-gray-200">
          <p className="font-semibold text-gray-900">{spot.name}</p>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200">
          <button
            onClick={() => setActiveTab('code')}
            className={`flex-1 py-3 px-4 font-medium transition ${
              activeTab === 'code'
                ? 'text-primary-600 border-b-2 border-primary-600 bg-primary-50'
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
            }`}
          >
            Enter Code
          </button>
          <button
            onClick={() => setActiveTab('qr')}
            className={`flex-1 py-3 px-4 font-medium transition ${
              activeTab === 'qr'
                ? 'text-primary-600 border-b-2 border-primary-600 bg-primary-50'
                : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
            }`}
          >
            Scan QR
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {/* Error message */}
          {error && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-800 text-sm font-medium">{error}</p>
            </div>
          )}

          {/* Enter Code Tab */}
          {activeTab === 'code' && (
            <form onSubmit={handleFormSubmit} className="space-y-4">
              <div>
                <label htmlFor="claim-code" className="block text-sm font-medium text-gray-700 mb-2">
                  Cache Code
                </label>
                <input
                  id="claim-code"
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  placeholder="Enter code from cache"
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent text-base"
                  disabled={isSubmitting}
                  autoFocus
                />
              </div>

              <button
                type="submit"
                disabled={!code.trim() || isSubmitting}
                className="w-full bg-primary-600 hover:bg-primary-700 disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-lg transition shadow-lg hover:shadow-xl disabled:cursor-not-allowed"
                style={{ minHeight: '48px' }}
              >
                {isSubmitting ? (
                  <span className="flex items-center justify-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Claiming...
                  </span>
                ) : (
                  'Claim Cache'
                )}
              </button>
            </form>
          )}

          {/* Scan QR Tab */}
          {activeTab === 'qr' && (
            <div className="space-y-4">
              <div className="text-center">
                <p className="text-sm text-gray-600 mb-4">
                  Position the QR code within the frame to scan
                </p>
                
                {/* QR Scanner container */}
                <div 
                  id="qr-reader" 
                  className="mx-auto rounded-lg overflow-hidden bg-black"
                  style={{ maxWidth: '100%' }}
                ></div>

                {isScanning && (
                  <div className="mt-4">
                    <div className="inline-flex items-center gap-2 text-sm text-gray-600">
                      <svg className="animate-spin h-4 w-4 text-primary-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      <span>Scanning...</span>
                    </div>
                  </div>
                )}

                {isSubmitting && (
                  <div className="mt-4">
                    <div className="inline-flex items-center gap-2 text-sm text-green-600 font-medium">
                      <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      <span>Claiming cache...</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
