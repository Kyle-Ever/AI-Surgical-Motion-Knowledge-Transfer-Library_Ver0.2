// Test data generators for Playwright tests

export const testData = {
  // Video test data
  videos: {
    valid: {
      id: 'test-video-1',
      filename: 'surgery_test.mp4',
      original_filename: 'surgery_test.mp4',
      upload_date: new Date().toISOString(),
      duration: 600,
      fps: 30,
      width: 1920,
      height: 1080,
      file_size: 104857600, // 100MB
      file_path: '/data/uploads/test-video-1.mp4',
      video_type: 'external',
      surgery_name: 'Test Surgery',
      surgeon_name: 'Dr. Test',
      surgery_date: '2025-01-14',
      memo: 'Test video for E2E testing'
    },
    invalid: {
      wrongFormat: {
        filename: 'document.pdf',
        mimeType: 'application/pdf'
      },
      oversized: {
        filename: 'huge_video.mp4',
        file_size: 2147483649 // Over 2GB limit
      }
    }
  },

  // Analysis test data
  analysis: {
    pending: {
      id: 'analysis-pending-1',
      video_id: 'test-video-1',
      status: 'PENDING',
      progress: 0,
      current_step: 'Waiting to start'
    },
    processing: {
      id: 'analysis-processing-1',
      video_id: 'test-video-1',
      status: 'PROCESSING',
      progress: 50,
      current_step: 'Skeleton detection',
      steps: [
        { name: 'Preprocessing', status: 'completed', progress: 100 },
        { name: 'Video info', status: 'completed', progress: 100 },
        { name: 'Frame extraction', status: 'completed', progress: 100 },
        { name: 'Skeleton detection', status: 'processing', progress: 50 },
        { name: 'Motion analysis', status: 'pending' },
        { name: 'Score calculation', status: 'pending' },
        { name: 'Data saving', status: 'pending' }
      ]
    },
    completed: {
      id: 'analysis-completed-1',
      video_id: 'test-video-1',
      status: 'COMPLETED',
      progress: 100,
      completed_at: new Date().toISOString(),
      avg_velocity: 15.5,
      max_velocity: 45.2,
      total_distance: 1850.3,
      total_frames: 3000,
      skeleton_data: {
        frames: Array.from({ length: 10 }, (_, i) => ({
          frame_number: i * 100,
          timestamp: i * 3.33,
          left_hand: { x: Math.random(), y: Math.random() },
          right_hand: { x: Math.random(), y: Math.random() }
        }))
      },
      scores: {
        speed: 78,
        accuracy: 82,
        stability: 75,
        efficiency: 80
      }
    },
    failed: {
      id: 'analysis-failed-1',
      video_id: 'test-video-1',
      status: 'FAILED',
      error_message: 'Video processing failed: Invalid frame format'
    }
  },

  // User data
  users: {
    testUser: {
      name: 'Test User',
      email: 'test@example.com',
      role: 'surgeon'
    }
  },

  // Error responses
  errors: {
    serverError: {
      status: 500,
      detail: 'Internal Server Error'
    },
    notFound: {
      status: 404,
      detail: 'Resource not found'
    },
    badRequest: {
      status: 400,
      detail: 'Invalid request parameters'
    },
    timeout: {
      status: 408,
      detail: 'Request timeout'
    },
    unauthorized: {
      status: 401,
      detail: 'Unauthorized access'
    }
  },

  // WebSocket messages
  wsMessages: {
    connected: {
      type: 'connection',
      status: 'connected'
    },
    progress: (progress: number, step: string) => ({
      type: 'progress',
      progress,
      step,
      message: `Processing: ${step}`
    }),
    completed: {
      type: 'completed',
      status: 'success',
      message: 'Analysis completed successfully'
    },
    error: {
      type: 'error',
      status: 'failed',
      message: 'Analysis failed'
    }
  }
}

// Helper function to create mock file
export function createMockFile(
  name: string = 'test-video.mp4',
  size: number = 1024 * 1024, // 1MB default
  type: string = 'video/mp4'
): { name: string; mimeType: string; buffer: Buffer } {
  // Playwright has a 50MB buffer limit, so cap the size
  const maxSize = 50 * 1024 * 1024 // 50MB
  const actualSize = Math.min(size, maxSize)

  return {
    name,
    mimeType: type,
    buffer: Buffer.alloc(actualSize, 'test-data')
  }
}

// Helper function to generate random analysis data
export function generateAnalysisData(frameCount: number = 100) {
  return {
    frames: Array.from({ length: frameCount }, (_, i) => ({
      frame_number: i,
      timestamp: i * 0.033, // 30fps
      skeleton: {
        left_hand: {
          x: 0.5 + Math.sin(i * 0.1) * 0.3,
          y: 0.5 + Math.cos(i * 0.1) * 0.3
        },
        right_hand: {
          x: 0.5 + Math.sin(i * 0.1 + Math.PI) * 0.3,
          y: 0.5 + Math.cos(i * 0.1 + Math.PI) * 0.3
        }
      },
      velocity: Math.abs(Math.sin(i * 0.05)) * 30 + 10,
      angle: {
        thumb: 45 + Math.sin(i * 0.1) * 20,
        index: 50 + Math.cos(i * 0.1) * 25,
        middle: 55 + Math.sin(i * 0.15) * 20,
        ring: 60 + Math.cos(i * 0.15) * 15,
        pinky: 65 + Math.sin(i * 0.2) * 10
      }
    }))
  }
}