import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import meditationBg from "@/assets/meditation-silhouette.jpg";

const DEFAULT_YOGA_PLAN = {
  name: "Quick Start Yoga",
  poses: [
    "Tree_Pose_or_Vrksasana_",
    "Warrior_I_Pose_or_Virabhadrasana_I_",
    "Warrior_II_Pose_or_Virabhadrasana_II_",
    "Chair_Pose_or_Utkatasana_",
    "Bound_Angle_Pose_or_Baddha_Konasana_",
    "Corpse_Pose_or_Savasana_",
  ],
  hold_times: [20, 20, 20, 20, 20, 30],
};

const YogaPage = () => {
  const navigate = useNavigate();

  useEffect(() => {
    // Check if user has a yoga plan
    const savedPlan = localStorage.getItem("userYogaPlan");
    if (savedPlan) {
      try {
        const plan = JSON.parse(savedPlan);
        if (plan.poses && plan.poses.length > 0) {
          // Navigate to yoga session with the saved plan
          navigate("/yoga-session", { state: { plan } });
          return;
        }
      } catch (e) {
        console.error("Error parsing saved plan:", e);
      }
    }
    
    // "Skip to Practice" deliberately bypasses onboarding. Give that path a
    // usable plan instead of bouncing the user back to onboarding forever.
    localStorage.setItem("userYogaPlan", JSON.stringify(DEFAULT_YOGA_PLAN));
    navigate("/yoga-session", { state: { plan: DEFAULT_YOGA_PLAN } });
  }, [navigate]);

  // Show loading while redirecting
  return (
    <div className="fixed inset-0">
      <div 
        className="absolute inset-0 bg-cover bg-center"
        style={{ backgroundImage: `url(${meditationBg})` }}
      >
        <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-[hsl(var(--gradient-yoga-start))]/40 to-black/50" />
      </div>
      <div className="relative z-10 h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-white mx-auto mb-4"></div>
          <p className="text-white text-xl">Loading yoga session...</p>
        </div>
      </div>
    </div>
  );
};

export default YogaPage;
