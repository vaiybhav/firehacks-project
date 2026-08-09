import { useState, useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Pause, Play, Volume2, VolumeX } from "lucide-react";
import { io, Socket } from "socket.io-client";
import meditationBg from "@/assets/meditation-silhouette.jpg";


interface YogaPlan {
  name: string;
  poses: string[];
  hold_times: number[];
}

interface SessionStatistics {
  accuracyScore: number;
  progressScore: number;
  repCount: number;
  avgHoldDuration: number;
  maxHoldDuration: number;
  avgHoldRatio: number;
  avgFormScore: number;
  correctionsCount: number;
  dangerousCorrections: number;
  improvableCorrections: number;
  consistencyScore: number;
  sessionDuration: number;
  poseEntries: number;
}

interface DebugInfo {
  detected_pose?: string;
  target_pose?: string;
  pose_confidence?: number;
  angle_similarity?: number;
  combined_score?: number;
  has_template?: boolean;
  exact_match?: boolean;
  body_fully_visible?: boolean;
  stability_frames?: number;
  stability_required?: number;
  smoothed_score?: number;
  can_start_timer?: boolean;
  is_matching_pose?: boolean;
}

interface SessionState {
  currentPoseIndex: number;
  currentPose: string;
  holdTime: number;
  elapsedTime: number;
  isInPose: boolean;
  poseStatus: "correct" | "improvable" | "wrong" | "unknown";
  feedback: string;
  readyCountdown: number;
  sessionActive: boolean;
  statistics: SessionStatistics | null;
  debugInfo: DebugInfo | null;  // Debug information
  videoFrame?: string | null; // Video frame data
  referenceCoach: {
    available: boolean;
    instruction: string;
    update_interval: number;
  } | null;
}

const YogaSessionPage = () => {
  const navigate = useNavigate();
  const location = useLocation();

  // Get plan from location state or localStorage
  const planFromState = location.state?.plan;
  const planFromStorage = localStorage.getItem("userYogaPlan");

  let plan: YogaPlan;
  if (planFromState) {
    plan = planFromState;
  } else if (planFromStorage) {
    try {
      plan = JSON.parse(planFromStorage);
    } catch {
      plan = { name: "Default", poses: [], hold_times: [] };
    }
  } else {
    plan = { name: "Default", poses: [], hold_times: [] };
  }

  const [sessionState, setSessionState] = useState<SessionState>({
    currentPoseIndex: 0,
    currentPose: plan.poses?.[0] || "",
    holdTime: plan.hold_times?.[0] || 20,
    elapsedTime: 0,
    isInPose: false,
    poseStatus: "unknown",
    feedback: "",
    readyCountdown: 0,
    sessionActive: false,
    statistics: null,
    debugInfo: null,  // Debug information
    referenceCoach: null,
  });

  const [isPaused, setIsPaused] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [videoFrame, setVideoFrame] = useState<string | null>(null);
  const [availableCameras, setAvailableCameras] = useState<Array<{ id: number, name: string, width: number, height: number }>>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<number>(0);
  const [loadingCameras, setLoadingCameras] = useState(false);
  const [voiceCoachingEnabled, setVoiceCoachingEnabled] = useState(true);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const socketRef = useRef<Socket | null>(null);
  const loadingRef = useRef(false);
  const cameraActiveRef = useRef(false);
  const videoRef = useRef<HTMLImageElement | null>(null);
  const lastSpokenCoachCueRef = useRef("");
  const lastSpokenCoachTimeRef = useRef(0);

  // Redirect to onboarding if no plan
  useEffect(() => {
    if (!plan?.poses || plan.poses.length === 0) {
      navigate("/onboarding");
    }
  }, [plan, navigate]);

  // Fetch available cameras
  const fetchCameras = async () => {
    setLoadingCameras(true);
    try {
      const response = await fetch("http://localhost:5002/list-cameras");
      if (response.ok) {
        const data = await response.json();
        if (data.cameras && data.cameras.length > 0) {
          setAvailableCameras(data.cameras);
          setSelectedCameraId(data.cameras[0].id);
        }
      }
    } catch (error) {
      console.error("Error fetching cameras:", error);
    } finally {
      setLoadingCameras(false);
    }
  };

  // Fetch cameras on mount
  useEffect(() => {
    fetchCameras();
  }, []);

  // Format pose name for display
  const formatPoseName = (pose: string) => {
    return pose
      .replace(/_/g, " ")
      .replace(/or/g, "|")
      .replace(/\s+/g, " ")
      .trim();
  };

  // Start yoga session
  const startSession = async () => {
    setLoading(true);
    loadingRef.current = true;
    setSessionState(prev => ({ ...prev, sessionActive: true }));

    try {
      // Check if backend is available first
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);

      const healthCheck = await fetch("http://localhost:5002/health", {
        method: "GET",
        signal: controller.signal,
      }).catch(() => {
        clearTimeout(timeoutId);
        return null;
      });
      clearTimeout(timeoutId);

      if (!healthCheck || !healthCheck.ok) {
        throw new Error("Yoga backend server is not running. Please start it with: ./start_yoga_web.sh");
      }

      // Start backend yoga session
      const sessionController = new AbortController();
      const sessionTimeoutId = setTimeout(() => sessionController.abort(), 20000); // Increased to 20 seconds for camera initialization

      const response = await fetch("http://localhost:5002/start-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan, camera_id: selectedCameraId }),
        signal: sessionController.signal,
      }).catch((error) => {
        clearTimeout(sessionTimeoutId);
        if (error.name === 'AbortError') {
          throw new Error("Request timeout. Camera initialization may be slow. Please try again.");
        }
        throw new Error(`Failed to connect: ${error.message}`);
      });
      clearTimeout(sessionTimeoutId);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage = errorData.message || errorData.error || `Failed to start session (${response.status})`;
        console.error("Start session error:", errorData);
        throw new Error(errorMessage);
      }

      // Connect Socket.IO for real-time updates
      const socket = io("http://localhost:5002", {
        timeout: 5000,
        transports: ['websocket', 'polling'],
      });
      socketRef.current = socket;

      // Store timeout reference for cleanup
      let connectionTimeoutRef: NodeJS.Timeout | null = null;

      // Set up timeout BEFORE connect handler
      connectionTimeoutRef = setTimeout(() => {
        if (loadingRef.current && !cameraActiveRef.current) {
          setLoading(false);
          loadingRef.current = false;
          setSessionState(prev => ({ ...prev, sessionActive: false }));
          if (socketRef.current) {
            socketRef.current.disconnect();
          }
          alert("Connection timeout. Please check if the backend is running.");
        }
      }, 10000);

      socket.on("connect", () => {
        console.log("✅ Socket.IO connected - ready to receive video frames");
        if (connectionTimeoutRef) {
          clearTimeout(connectionTimeoutRef);
          connectionTimeoutRef = null;
        }
        setLoading(false);
        loadingRef.current = false;
        setCameraActive(true);
        cameraActiveRef.current = true;
      });

      socket.on("connected", (data: any) => {
        console.log("✅ Server confirmed connection:", data);
      });

      socket.on("session_update", (data: any) => {
        try {
          // Log video frame in session_update
          if (data?.videoFrame || data?.video_frame) {
            const frame = data.videoFrame || data.video_frame;
            console.log(`📹 Video frame in session_update: ${frame?.length || 0} chars`);
          }

          // Safely extract all values with fallbacks
          const holdTime = data.holdTime ?? data.hold_time ?? data.target_hold ?? 20;
          const elapsedTime = data.elapsedTime ?? data.elapsed_time ?? 0;

          // Extract statistics if provided - ensure all values are numbers
          const statistics = data.statistics ? {
            accuracyScore: typeof data.statistics.accuracyScore === 'number' ? data.statistics.accuracyScore : 0,
            progressScore: typeof data.statistics.progressScore === 'number' ? data.statistics.progressScore : 0,
            repCount: typeof data.statistics.repCount === 'number' ? data.statistics.repCount : 0,
            avgHoldDuration: typeof data.statistics.avgHoldDuration === 'number' ? data.statistics.avgHoldDuration : 0,
            maxHoldDuration: typeof data.statistics.maxHoldDuration === 'number' ? data.statistics.maxHoldDuration : 0,
            avgHoldRatio: typeof data.statistics.avgHoldRatio === 'number' ? data.statistics.avgHoldRatio : 0,
            avgFormScore: typeof data.statistics.avgFormScore === 'number' ? data.statistics.avgFormScore : 0,
            correctionsCount: typeof data.statistics.correctionsCount === 'number' ? data.statistics.correctionsCount : 0,
            dangerousCorrections: typeof data.statistics.dangerousCorrections === 'number' ? data.statistics.dangerousCorrections : 0,
            improvableCorrections: typeof data.statistics.improvableCorrections === 'number' ? data.statistics.improvableCorrections : 0,
            consistencyScore: typeof data.statistics.consistencyScore === 'number' ? data.statistics.consistencyScore : 0,
            sessionDuration: typeof data.statistics.sessionDuration === 'number' ? data.statistics.sessionDuration : 0,
            poseEntries: typeof data.statistics.poseEntries === 'number' ? data.statistics.poseEntries : 0,
          } : null;

          setSessionState((prev) => {
            // Use backend elapsedTime directly - backend calculates it consistently every frame
            const newElapsedTime = data.elapsedTime ?? data.elapsed_time ?? 0;

            return {
              ...prev,
              currentPoseIndex: data.currentPoseIndex ?? prev.currentPoseIndex,
              currentPose: data.currentPose ?? prev.currentPose,
              holdTime: holdTime,
              isInPose: data.isInPose ?? prev.isInPose,
              poseStatus: data.poseStatus ?? prev.poseStatus,
              feedback: data.feedback ?? prev.feedback,
              readyCountdown: data.readyCountdown ?? data.ready_countdown ?? prev.readyCountdown,
              elapsedTime: newElapsedTime,  // Use backend value directly - no stabilization needed
              statistics: statistics ?? prev.statistics, // Keep previous stats if not provided
              debugInfo: data.debugInfo ?? data.debug_info ?? prev.debugInfo,  // Add debug info
              referenceCoach: data.referenceCoach ?? data.reference_coach ?? prev.referenceCoach,
            };
          });

          // Update video frame if provided
          if (data?.videoFrame || data?.video_frame) {
            try {
              const frame = data.videoFrame || data.video_frame;
              if (frame && typeof frame === 'string' && frame.length > 0) {
                const dataUrl = frame.startsWith('data:') ? frame : `data:image/jpeg;base64,${frame}`;
                setVideoFrame(dataUrl);
                console.log(`✅ Video frame received in session_update: ${frame.length} chars`);
              } else {
                console.warn("⚠️ Empty or invalid video frame in session_update", { frame, type: typeof frame });
              }
            } catch (e) {
              console.error("Error setting video frame:", e);
            }
          } else {
            // Only warn occasionally to avoid spam
            if (!sessionState.videoFrame) {
              console.warn("⚠️ No videoFrame in session_update", Object.keys(data));
            }
          }
        } catch (error) {
          console.error("Error processing session_update:", error);
          // Don't crash the session, just log the error
        }
      });

      socket.on("video_frame", (data: any) => {
        // Update video frame even if no pose info
        console.log("📹 video_frame event received", {
          hasData: !!data,
          hasFrame: !!data?.frame,
          frameType: typeof data?.frame,
          frameLength: data?.frame?.length
        });

        if (data?.frame && typeof data.frame === 'string' && data.frame.length > 0) {
          const dataUrl = data.frame.startsWith('data:') ? data.frame : `data:image/jpeg;base64,${data.frame}`;
          console.log(`✅ Setting video frame: ${data.frame.length} chars, dataUrl length: ${dataUrl.length}`);
          setVideoFrame(dataUrl);
        } else {
          console.warn("⚠️ Empty or invalid video_frame event", {
            hasData: !!data,
            hasFrame: !!data?.frame,
            frameType: typeof data?.frame,
            frameLength: data?.frame?.length
          });
        }
      });

      socket.on("debug_update", (data: any) => {
        // Update debug info separately for faster updates
        try {
          if (data && data.debugInfo) {
            setSessionState((prev) => ({
              ...prev,
              debugInfo: data.debugInfo,
            }));
          }
        } catch (error) {
          console.error("Error updating debug info:", error);
        }
      });

      // Handle pose change event from backend
      socket.on("pose_changed", (data: any) => {
        console.log("🔄 Pose changed:", data);
        setSessionState((prev) => ({
          ...prev,
          currentPoseIndex: data.currentPoseIndex ?? prev.currentPoseIndex,
          currentPose: data.currentPose ?? prev.currentPose,
          holdTime: data.holdTime ?? prev.holdTime,
          elapsedTime: 0,  // Reset timer for new pose
          isInPose: false,  // Reset pose status
          poseStatus: "unknown",
          feedback: "",
        }));
      });

      // Handle session complete
      socket.on("session_complete", (data: any) => {
        alert("🎉 All poses completed! Great job!");
        endSession();
      });

      socket.on("error", (data: any) => {
        console.error("❌ Backend error received:", data);
        const errorMessage = data?.message || "Unknown error from backend";
        console.error("Error details:", errorMessage);
        setLoading(false);
        loadingRef.current = false;
        setSessionState(prev => ({ ...prev, sessionActive: false }));
        alert(`Backend Error: ${errorMessage}\n\nCheck the backend terminal for detailed error messages.`);
      });

      socket.on("connect_error", (error: any) => {
        console.error("Socket connection error:", error);
        setLoading(false);
        loadingRef.current = false;
        setSessionState(prev => ({ ...prev, sessionActive: false }));
        alert("Failed to connect to yoga backend. Please make sure ./start_yoga_web.sh is running.");
      });

      socket.on("disconnect", () => {
        console.log("Socket.IO disconnected");
        setCameraActive(false);
        cameraActiveRef.current = false;
      });

    } catch (error: any) {
      console.error("Failed to start session:", error);
      setLoading(false);
      loadingRef.current = false;
      setSessionState(prev => ({ ...prev, sessionActive: false }));
      alert(error.message || "Failed to start yoga session. Make sure the backend is running with: ./start_yoga_web.sh");
    }
  };

  // Timer effect - REMOVED: Use backend elapsedTime only, don't increment locally
  // The backend sends elapsedTime updates every frame, so we don't need local incrementing
  // This prevents conflicts and ensures consistency
  useEffect(() => {
    // Clear any existing interval - we rely on backend updates only
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  // Speak the same stabilized, plain-language cue shown beside the camera.
  // Browser speech keeps this feature local and does not require an API key.
  useEffect(() => {
    const instruction = sessionState.referenceCoach?.instruction?.trim() || "";
    const isHoldMessage = instruction.toLowerCase().includes("within range");
    if (isHoldMessage) {
      // Once the user settles into range, allow the same cue to be spoken
      // again later if they drift back out of alignment.
      lastSpokenCoachCueRef.current = "";
      return;
    }
    const canSpeak =
      voiceCoachingEnabled &&
      sessionState.sessionActive &&
      sessionState.readyCountdown === 0 &&
      !isPaused &&
      instruction.length > 0 &&
      !isHoldMessage &&
      "speechSynthesis" in window;

    if (!canSpeak || instruction === lastSpokenCoachCueRef.current) return;

    const now = Date.now();
    const minimumGapMs = 6000;
    if (now - lastSpokenCoachTimeRef.current < minimumGapMs) return;
    if (window.speechSynthesis.speaking || window.speechSynthesis.pending) return;

    const utterance = new SpeechSynthesisUtterance(instruction);
    utterance.rate = 0.92;
    utterance.pitch = 1;
    utterance.volume = 1;
    window.speechSynthesis.speak(utterance);
    lastSpokenCoachCueRef.current = instruction;
    lastSpokenCoachTimeRef.current = now;
  }, [
    sessionState.referenceCoach?.instruction,
    sessionState.sessionActive,
    sessionState.readyCountdown,
    voiceCoachingEnabled,
    isPaused,
  ]);

  // Keyboard controls: N=next, Q=quit, R=repeat, Space=pause
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      // Ignore if typing in input fields
      if ((e.target as HTMLElement)?.tagName === 'INPUT' || (e.target as HTMLElement)?.tagName === 'TEXTAREA') {
        return;
      }

      if (e.key.toLowerCase() === 'n' && sessionState.sessionActive) {
        nextPose();
      } else if (e.key.toLowerCase() === 'q' && sessionState.sessionActive) {
        endSession();
      } else if (e.key.toLowerCase() === 'r' && sessionState.sessionActive) {
        repeatInstruction();
      } else if (e.key === ' ' && sessionState.sessionActive) {
        e.preventDefault();
        togglePause();
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [sessionState.sessionActive]);

  // Repeat instruction
  const repeatInstruction = () => {
    if (socketRef.current && sessionState.sessionActive) {
      socketRef.current.emit('repeat_instruction');
    }
  };

  // Toggle pause
  const togglePause = () => {
    const newPausedState = !isPaused;
    setIsPaused(newPausedState);

    if (newPausedState && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }

    if (socketRef.current) {
      if (newPausedState) {
        socketRef.current.emit('pause_session');
      } else {
        socketRef.current.emit('resume_session');
      }
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
      // Release the backend camera even if the user closes/navigates away from
      // the page without pressing the explicit End Session button.
      fetch("http://localhost:5002/stop-session", {
        method: "POST",
        keepalive: true,
      }).catch(() => undefined);
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  // Next pose - SKIP TO NEXT POSE
  const nextPose = () => {
    // Always send next_pose command to backend
    // Backend will handle the pose change and emit pose_changed event
    if (socketRef.current && sessionState.sessionActive) {
      socketRef.current.emit("next_pose");
      console.log("➡️  Skipping to next pose...");
    }
  };

  // End session
  const endSession = async () => {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
    if (socketRef.current) {
      socketRef.current.emit("end_session");
    }

    // Stop backend session and get final statistics
    try {
      const response = await fetch("http://localhost:5002/stop-session", { method: "POST" });
      const data = await response.json();

      // Save final statistics to localStorage for progress page
      if (data.finalStatistics) {
        const savedStats = JSON.parse(localStorage.getItem("yogaSessionStats") || "[]");
        savedStats.push({
          ...data.finalStatistics,
          timestamp: new Date().toISOString(),
          planName: plan.name,
        });
        localStorage.setItem("yogaSessionStats", JSON.stringify(savedStats));
      }
    } catch (error) {
      console.error("Error stopping session:", error);
    }

    if (socketRef.current) {
      socketRef.current.disconnect();
    }

    navigate("/menu");
  };

  const progress = sessionState.holdTime > 0 ? (sessionState.elapsedTime / sessionState.holdTime) * 100 : 0;
  const remainingTime = Math.max(0, (sessionState.holdTime || 0) - (sessionState.elapsedTime || 0));

  // Get status color
  const getStatusColor = () => {
    if (sessionState.isInPose) return "bg-emerald-400";
    switch (sessionState.poseStatus) {
      case "correct":
        return "bg-green-500";
      case "improvable":
        return "bg-yellow-500";
      case "wrong":
        return "bg-red-500";
      default:
        return "bg-gray-400";
    }
  };

  // Get status text
  const getStatusText = () => {
    if (sessionState.isInPose) return "Looking good";
    switch (sessionState.poseStatus) {
      case "correct":
        return "Perfect Form!";
      case "improvable":
        return "Good, but can improve";
      case "wrong":
        return "Adjust your pose";
      default:
        return "Getting ready...";
    }
  };

  if (!plan?.poses || plan.poses.length === 0) {
    return null; // Will redirect via useEffect
  }

  if (!sessionState.sessionActive) {
    return (
      <div
        className="min-h-screen relative flex items-center justify-center px-8"
        style={{
          backgroundImage: `url(${meditationBg})`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="absolute inset-0 bg-black/60" />
        <div className="relative z-10 max-w-2xl w-full text-center">
          <h2 className="text-4xl font-light text-white mb-6">
            Ready to Begin?
          </h2>
          <p className="text-white/80 text-lg mb-8">
            {plan.poses?.length || 0} poses • {plan.hold_times && plan.hold_times.length > 0 ? Math.round(plan.hold_times.reduce((a, b) => (a || 0) + (b || 0), 0) / 60) : 0} minutes
          </p>

          {/* Camera Selection */}
          {availableCameras.length > 0 && (
            <div className="mb-6 bg-white/10 backdrop-blur-md rounded-lg p-4 border border-white/20">
              <label className="block text-white/90 text-sm mb-2 text-left">
                Select Camera:
              </label>
              <select
                value={selectedCameraId}
                onChange={(e) => setSelectedCameraId(Number(e.target.value))}
                className="w-full bg-white/20 text-white border border-white/30 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-white/50"
              >
                {availableCameras.map((cam) => (
                  <option key={cam.id} value={cam.id} className="bg-gray-800">
                    {cam.name} ({cam.width}x{cam.height})
                  </option>
                ))}
              </select>
            </div>
          )}

          {loadingCameras && (
            <div className="mb-6 text-white/60 text-sm">
              Loading cameras...
            </div>
          )}

          <div className="flex gap-4 justify-center">
            <Button
              onClick={() => navigate("/menu")}
              className="bg-white/10 hover:bg-white/20 text-white border border-white/30"
            >
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
            <Button
              onClick={startSession}
              className="bg-white/20 hover:bg-white/30 text-white border border-white/30 text-lg px-8 py-6"
              size="lg"
            >
              Start Session
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div
        className="min-h-screen relative flex items-center justify-center"
        style={{
          backgroundImage: `url(${meditationBg})`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="absolute inset-0 bg-black/60" />
        <div className="relative z-10 text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-white mx-auto mb-4"></div>
          <p className="text-white text-xl">Loading yoga session...</p>
        </div>
      </div>
    );
  }

  const toggleVoiceCoaching = () => {
    setVoiceCoachingEnabled((enabled) => {
      if (enabled && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
      if (!enabled) {
        lastSpokenCoachCueRef.current = "";
        lastSpokenCoachTimeRef.current = 0;
      }
      return !enabled;
    });
  };

  return (
    <div className="min-h-screen bg-[#0d100f] text-white">
      <header className="border-b border-white/10 bg-[#0d100f]/95">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-4 px-4 py-4 md:px-8">
          <Button
            onClick={endSession}
            variant="ghost"
            className="text-white/70 hover:bg-white/10 hover:text-white"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            End session
          </Button>

          <div className="text-center">
            <p className="text-xs uppercase tracking-[0.18em] text-white/45">
              Pose {sessionState.currentPoseIndex + 1} of {plan?.poses?.length || 0}
            </p>
            <h1 className="mt-1 text-lg font-medium md:text-xl">
              {formatPoseName(sessionState.currentPose)}
            </h1>
          </div>

          <div className="flex min-w-[100px] items-center justify-end gap-2 text-xs text-white/50">
            <span className={`h-2 w-2 rounded-full ${cameraActive ? "bg-emerald-400" : "bg-white/30"}`} />
            {cameraActive ? "Camera on" : "Connecting"}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1500px] px-4 py-5 md:px-8 md:py-7">
        <section>
            <div className="relative aspect-video overflow-hidden rounded-2xl border border-white/10 bg-black shadow-[0_20px_60px_rgba(0,0,0,0.25)]">
              {videoFrame ? (
                <img
                  ref={videoRef}
                  src={videoFrame}
                  alt="Mirrored yoga coaching camera"
                  className="h-full w-full object-contain"
                  onError={(error) => console.error("Camera frame failed to load", error)}
                />
              ) : (
                <div className="flex h-full items-center justify-center text-center">
                  <div>
                    <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-white/20 border-t-white/80" />
                    <p className="text-sm text-white/55">Waiting for camera feed…</p>
                  </div>
                </div>
              )}

              <div className="absolute left-4 top-4 flex items-center gap-2 rounded-full bg-black/60 px-3 py-2 text-sm backdrop-blur-md">
                <span className={`h-2.5 w-2.5 rounded-full ${getStatusColor()}`} />
                <span>{getStatusText()}</span>
              </div>

              <div className="absolute bottom-4 left-4 rounded-xl bg-black/65 px-4 py-3 backdrop-blur-md">
                <p className="text-3xl font-light tabular-nums">{remainingTime}s</p>
                <p className="mt-0.5 text-xs text-white/55">remaining</p>
              </div>

              {sessionState.readyCountdown > 0 && (
                <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/45 backdrop-blur-[2px]">
                  <div className="text-center">
                    <p className="text-sm uppercase tracking-[0.25em] text-white/65">Get ready</p>
                    <p className="mt-2 text-8xl font-light tabular-nums text-white">
                      {sessionState.readyCountdown}
                    </p>
                  </div>
                </div>
              )}

              <aside className="absolute right-4 top-1/2 hidden w-80 -translate-y-1/2 flex-col rounded-2xl border border-white/15 bg-black/65 p-5 shadow-2xl backdrop-blur-xl md:flex">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs uppercase tracking-[0.18em] text-white/50">Coach</p>
                  <button
                    type="button"
                    onClick={toggleVoiceCoaching}
                    className="rounded-full bg-white/10 p-2 text-white/70 transition hover:bg-white/15 hover:text-white"
                    aria-label={voiceCoachingEnabled ? "Mute voice coaching" : "Enable voice coaching"}
                    title={voiceCoachingEnabled ? "Mute voice coaching" : "Enable voice coaching"}
                  >
                    {voiceCoachingEnabled ? <Volume2 size={17} /> : <VolumeX size={17} />}
                  </button>
                </div>
                <p className="mt-6 text-xl font-light leading-snug text-white">
                  {sessionState.isInPose
                    ? "Nice work — keep holding."
                    : sessionState.referenceCoach?.instruction || "Finding your reference points…"}
                </p>
                {sessionState.feedback && !sessionState.isInPose && (
                  <p className="mt-3 text-sm leading-relaxed text-white/55">{sessionState.feedback}</p>
                )}
                <p className="mt-6 text-xs text-white/35">
                  {voiceCoachingEnabled ? "Voice on" : "Voice muted"} · swipe right to skip
                </p>
              </aside>
            </div>

            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
              <div
                className="h-full rounded-full bg-emerald-400 transition-[width] duration-300"
                style={{ width: `${Math.min(Math.max(progress, 0), 100)}%` }}
              />
            </div>
          <aside className="mt-4 flex flex-col rounded-2xl border border-white/10 bg-white/[0.04] p-5 md:hidden">
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs uppercase tracking-[0.18em] text-white/45">Coach</p>
              <button
                type="button"
                onClick={toggleVoiceCoaching}
                className="rounded-full border border-white/10 bg-white/[0.05] p-2.5 text-white/65 transition hover:bg-white/10 hover:text-white"
                aria-label={voiceCoachingEnabled ? "Mute voice coaching" : "Enable voice coaching"}
                title={voiceCoachingEnabled ? "Mute voice coaching" : "Enable voice coaching"}
              >
                {voiceCoachingEnabled ? <Volume2 size={18} /> : <VolumeX size={18} />}
              </button>
            </div>

            <div className="py-5">
              <p className="text-2xl font-light leading-snug text-white/95">
                {sessionState.isInPose
                  ? "Nice work — keep holding."
                  : sessionState.referenceCoach?.instruction || "Finding your reference points…"}
              </p>
              {sessionState.feedback && !sessionState.isInPose && (
                <p className="mt-4 border-l-2 border-white/20 pl-3 text-sm leading-relaxed text-white/55">
                  {sessionState.feedback}
                </p>
              )}
            </div>

            <p className="text-xs leading-relaxed text-white/35">
              {voiceCoachingEnabled ? "Voice guidance on" : "Voice guidance muted"} · swipe right to skip
            </p>
          </aside>
        </section>

        <div className="mt-5 flex flex-wrap items-center justify-center gap-3 border-t border-white/10 pt-5">
          <Button
            onClick={togglePause}
            className="bg-white/10 text-white hover:bg-white/15"
          >
            {isPaused ? <Play className="mr-2 h-4 w-4" /> : <Pause className="mr-2 h-4 w-4" />}
            {isPaused ? "Resume" : "Pause"}
          </Button>

          {sessionState.currentPoseIndex < (plan?.poses?.length || 0) - 1 && (
            <Button
              onClick={nextPose}
              variant="ghost"
              className="text-white/65 hover:bg-white/10 hover:text-white"
            >
              Next pose →
            </Button>
          )}

          <Button
            onClick={repeatInstruction}
            variant="ghost"
            className="text-white/65 hover:bg-white/10 hover:text-white"
          >
            Repeat instruction
          </Button>
        </div>
      </main>
    </div>
  );
};

export default YogaSessionPage;
