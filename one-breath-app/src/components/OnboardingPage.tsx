import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import meditationBg from "@/assets/meditation-silhouette.jpg";

// The 24 poses from config
const AVAILABLE_POSES = [
  "Boat_Pose_or_Paripurna_Navasana_",
  "Bound_Angle_Pose_or_Baddha_Konasana_",
  "Cat_Cow_Pose_or_Marjaryasana_",
  "Chair_Pose_or_Utkatasana_",
  "Corpse_Pose_or_Savasana_",
  "Dolphin_Plank_Pose_or_Makara_Adho_Mukha_Svanasana_",
  "Extended_Puppy_Pose_or_Uttana_Shishosana_",
  "Extended_Revolved_Side_Angle_Pose_or_Utthita_Parsvakonasana_",
  "Four-Limbed_Staff_Pose_or_Chaturanga_Dandasana_",
  "Garland_Pose_or_Malasana_",
  "Gate_Pose_or_Parighasana_",
  "Happy_Baby_Pose_or_Ananda_Balasana_",
  "Locust_Pose_or_Salabhasana_",
  "Low_Lunge_pose_or_Anjaneyasana_",
  "Sitting pose 1 (normal)",
  "Staff_Pose_or_Dandasana_",
  "Plank_Pose_or_Kumbhakasana_",
  "Supta_Baddha_Konasana_",
  "Tree_Pose_or_Vrksasana_",
  "viparita_virabhadrasana_or_reverse_warrior_pose",
  "Virasana_or_Vajrasana",
  "Warrior_I_Pose_or_Virabhadrasana_I_",
  "Warrior_II_Pose_or_Virabhadrasana_II_",
  "Wind_Relieving_pose_or_Pawanmuktasana",
];

interface UserProfile {
  healthLevel: string;
  age: number;
  weight: number;
}

interface YogaPlan {
  name: string;
  poses: string[];
  hold_times: number[];
}

const DEFAULT_YOGA_PLAN: YogaPlan = {
  name: "Balanced Beginner Flow",
  poses: [
    "Cat_Cow_Pose_or_Marjaryasana_",
    "Extended_Puppy_Pose_or_Uttana_Shishosana_",
    "Low_Lunge_pose_or_Anjaneyasana_",
    "Warrior_II_Pose_or_Virabhadrasana_II_",
    "Tree_Pose_or_Vrksasana_",
    "Chair_Pose_or_Utkatasana_",
    "Garland_Pose_or_Malasana_",
    "Virasana_or_Vajrasana",
    "Supta_Baddha_Konasana_",
    "Corpse_Pose_or_Savasana_",
  ],
  hold_times: [12, 12, 15, 15, 15, 12, 12, 12, 15, 20],
};

const OnboardingPage = () => {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [healthLevel, setHealthLevel] = useState("");
  const [age, setAge] = useState("");
  const [weight, setWeight] = useState("");
  const [yogaPlan, setYogaPlan] = useState<YogaPlan | null>(null);

  const generateYogaPlan = (profile: UserProfile): YogaPlan => {
    const userAge = profile.age;
    const userWeight = profile.weight;
    const health = profile.healthLevel.toLowerCase();

    const gentleFlow = {
      name: "Gentle Floor Flow",
      poses: [
        "Cat_Cow_Pose_or_Marjaryasana_",
        "Extended_Puppy_Pose_or_Uttana_Shishosana_",
        "Virasana_or_Vajrasana",
        "Wind_Relieving_pose_or_Pawanmuktasana",
        "Supta_Baddha_Konasana_",
        "Corpse_Pose_or_Savasana_",
      ],
      holdTimes: [10, 12, 12, 12, 15, 20],
    };

    const balancedFlow = {
      name: "Balanced Beginner Flow",
      poses: DEFAULT_YOGA_PLAN.poses,
      holdTimes: DEFAULT_YOGA_PLAN.hold_times,
    };

    const activeFlow = {
      name: "Active Full-Body Flow",
      poses: [
        "Cat_Cow_Pose_or_Marjaryasana_",
        "Extended_Puppy_Pose_or_Uttana_Shishosana_",
        "Plank_Pose_or_Kumbhakasana_",
        "Low_Lunge_pose_or_Anjaneyasana_",
        "Warrior_II_Pose_or_Virabhadrasana_II_",
        "viparita_virabhadrasana_or_reverse_warrior_pose",
        "Chair_Pose_or_Utkatasana_",
        "Tree_Pose_or_Vrksasana_",
        "Garland_Pose_or_Malasana_",
        "Boat_Pose_or_Paripurna_Navasana_",
        "Supta_Baddha_Konasana_",
        "Corpse_Pose_or_Savasana_",
      ],
      holdTimes: [10, 10, 12, 15, 15, 12, 12, 15, 12, 12, 15, 20],
    };

    const selectedFlow =
      userAge >= 60 || health === "poor" || userWeight > 250
        ? gentleFlow
        : health === "excellent" && userAge < 40 && userWeight < 200
          ? activeFlow
          : balancedFlow;

    const selectedPoses = selectedFlow.poses.filter((pose) => AVAILABLE_POSES.includes(pose));
    const holdTimes = selectedFlow.holdTimes.slice(0, selectedPoses.length);

    return {
      name: selectedFlow.name,
      poses: selectedPoses,
      hold_times: holdTimes,
    };
  };

  const handleSubmit = () => {
    if (!healthLevel || !age || !weight) {
      alert("Please fill in all fields");
      return;
    }

    const profile: UserProfile = {
      healthLevel,
      age: parseInt(age),
      weight: parseFloat(weight),
    };

    const plan = generateYogaPlan(profile);
    setYogaPlan(plan);

    // Store in localStorage
    localStorage.setItem("userProfile", JSON.stringify(profile));
    localStorage.setItem("yogaPlan", JSON.stringify(plan));

    setStep(3);
  };

  if (step === 3 && yogaPlan) {
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
        <div className="relative z-10 max-w-2xl w-full bg-white/10 backdrop-blur-md rounded-2xl p-8 border border-white/20">
          <h2 className="text-4xl font-light text-white mb-6 text-center">
            Your Personalized Yoga Plan
          </h2>
          <div className="space-y-4 mb-8">
            <div className="bg-white/10 rounded-lg p-4">
              <p className="text-white/90 text-lg mb-2">
                <strong>Health Level:</strong> {healthLevel}
              </p>
              <p className="text-white/90 text-lg mb-2">
                <strong>Age:</strong> {age} years
              </p>
              <p className="text-white/90 text-lg">
                <strong>Weight:</strong> {weight} lbs
              </p>
            </div>
            <div className="bg-white/10 rounded-lg p-4">
              <p className="text-white/90 text-lg mb-4">
                <strong>Plan:</strong> {yogaPlan.poses.length} poses
              </p>
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {yogaPlan.poses.map((pose, idx) => (
                  <div key={idx} className="text-white/80 text-sm">
                    {idx + 1}. {pose.replace(/_/g, " ").replace(/or/g, "|")} ({yogaPlan.hold_times[idx]}s)
                  </div>
                ))}
              </div>
            </div>
          </div>
          <Button
            onClick={() => {
              // Save plan to localStorage and navigate to menu
              try {
                localStorage.setItem("userYogaPlan", JSON.stringify(yogaPlan));
                navigate("/yoga-session", { replace: true, state: { plan: yogaPlan } });
              } catch (error) {
                console.error("Navigation error:", error);
                // Fallback: try direct navigation
                window.location.href = "/yoga-session";
              }
            }}
            className="w-full bg-white/20 hover:bg-white/30 text-white border border-white/30 text-lg py-6"
            size="lg"
          >
            Start Yoga
          </Button>
        </div>
      </div>
    );
  }

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
      <div className="relative z-10 max-w-2xl w-full bg-white/10 backdrop-blur-md rounded-2xl p-8 border border-white/20">
        <h2 className="text-4xl font-light text-white mb-8 text-center">
          {step === 1 ? "Welcome to Horizons" : "Tell Us About Yourself"}
        </h2>

        {step === 1 ? (
          <div className="space-y-6">
            <p className="text-white/90 text-lg text-center">
              Let's create a personalized yoga plan just for you
            </p>
            <Button
              onClick={() => setStep(2)}
              className="w-full bg-white/20 hover:bg-white/30 text-white border border-white/30 text-lg py-6"
              size="lg"
            >
              Get Started
            </Button>
            <Button
              onClick={() => {
                localStorage.setItem("userYogaPlan", JSON.stringify(DEFAULT_YOGA_PLAN));
                navigate("/yoga-session", { state: { plan: DEFAULT_YOGA_PLAN } });
              }}
              className="w-full bg-white/10 hover:bg-white/20 text-white border border-white/20 text-sm py-3"
              variant="outline"
            >
              Skip Setup
            </Button>
          </div>
        ) : (
          <div className="space-y-6">
            <div>
              <label className="block text-white/90 text-lg mb-2">
                Health Level
              </label>
              <select
                value={healthLevel}
                onChange={(e) => setHealthLevel(e.target.value)}
                className="w-full bg-white/10 border border-white/30 rounded-lg px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-white/50"
              >
                <option value="">Select health level</option>
                <option value="excellent">Excellent</option>
                <option value="good">Good</option>
                <option value="fair">Fair</option>
                <option value="poor">Poor</option>
              </select>
            </div>

            <div>
              <label className="block text-white/90 text-lg mb-2">
                Age
              </label>
              <input
                type="number"
                value={age}
                onChange={(e) => setAge(e.target.value)}
                placeholder="Enter your age"
                className="w-full bg-white/10 border border-white/30 rounded-lg px-4 py-3 text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-white/50"
              />
            </div>

            <div>
              <label className="block text-white/90 text-lg mb-2">
                Weight (lbs)
              </label>
              <input
                type="number"
                value={weight}
                onChange={(e) => setWeight(e.target.value)}
                placeholder="Enter your weight in pounds"
                className="w-full bg-white/10 border border-white/30 rounded-lg px-4 py-3 text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-white/50"
              />
            </div>

            <div className="flex gap-4">
              <Button
                onClick={() => setStep(1)}
                className="flex-1 bg-white/10 hover:bg-white/20 text-white border border-white/30"
              >
                Back
              </Button>
              <Button
                onClick={handleSubmit}
                className="flex-1 bg-white/20 hover:bg-white/30 text-white border border-white/30"
                disabled={!healthLevel || !age || !weight}
              >
                Create Plan
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default OnboardingPage;
