import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Plus, Heart } from "lucide-react";
import { Button } from "@/components/ui/button";
import meditationBg from "@/assets/meditation-silhouette.jpg";
import {
  createCommunityPost,
  fetchCommunityPosts,
  type CommunityPost,
} from "@/lib/communityPosts";
import { isFirebaseConfigured } from "@/lib/firebase";

const CommunityPage = () => {
  const navigate = useNavigate();
  const [posts, setPosts] = useState<CommunityPost[]>([]);
  const [showStoryForm, setShowStoryForm] = useState(false);
  const [showBridgeForm, setShowBridgeForm] = useState(false);
  const [storyName, setStoryName] = useState("");
  const [storyText, setStoryText] = useState("");
  const [bridgeWho, setBridgeWho] = useState("");
  const [bridgeWhat, setBridgeWhat] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    void loadWall();
  }, []);

  const loadWall = async (refreshReddit = false) => {
    setLoading(true);
    setLoadError(null);
    try {
      const [firebasePosts, redditPosts] = await Promise.all([
        fetchUserPosts(),
        fetchRedditPosts(refreshReddit),
      ]);
      setPosts(
        [...firebasePosts, ...redditPosts].sort((a, b) => b.timestamp - a.timestamp)
      );
    } catch (error) {
      console.error("Error loading community wall:", error);
      setLoadError("Couldn't load the community wall. Try Refresh.");
      setPosts([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchUserPosts = async (): Promise<CommunityPost[]> => {
    if (!isFirebaseConfigured()) {
      return [];
    }
    try {
      return await fetchCommunityPosts(40);
    } catch (error) {
      console.error("Error loading Firebase posts:", error);
      setLoadError("Couldn't load saved posts from Firebase.");
      return [];
    }
  };

  const fetchRedditPosts = async (refresh = false): Promise<CommunityPost[]> => {
    try {
      const url = `/community-posts?limit=15${refresh ? "&refresh=1" : ""}`;
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`Community posts failed: ${response.status}`);
      }
      const data = await response.json();
      return (data.posts || []) as CommunityPost[];
    } catch (error) {
      console.error("Error loading Reddit posts:", error);
      // User posts from Firebase can still show if Reddit/API is down.
      return [];
    }
  };

  const submitStory = async () => {
    if (!storyText.trim() || saving) return;

    if (!isFirebaseConfigured()) {
      setLoadError("Firebase is not configured. Add VITE_FIREBASE_* env vars.");
      return;
    }

    setSaving(true);
    setLoadError(null);
    try {
      const newPost = await createCommunityPost({
        type: "story",
        name: storyName.trim() || "Anonymous",
        text: storyText.trim(),
      });
      setPosts((prev) => [newPost, ...prev]);
      setStoryName("");
      setStoryText("");
      setShowStoryForm(false);
    } catch (error) {
      console.error("Error posting story:", error);
      setLoadError("Couldn't save your story to Firebase.");
    } finally {
      setSaving(false);
    }
  };

  const submitBridge = async () => {
    if (!bridgeWhat.trim() || saving) return;

    if (!isFirebaseConfigured()) {
      setLoadError("Firebase is not configured. Add VITE_FIREBASE_* env vars.");
      return;
    }

    setSaving(true);
    setLoadError(null);
    try {
      const newPost = await createCommunityPost({
        type: "bridge",
        who: bridgeWho.trim() || "Someone",
        text: bridgeWhat.trim(),
      });
      setPosts((prev) => [newPost, ...prev]);
      setBridgeWho("");
      setBridgeWhat("");
      setShowBridgeForm(false);
    } catch (error) {
      console.error("Error posting bridge:", error);
      setLoadError("Couldn't save your yoga bridge to Firebase.");
    } finally {
      setSaving(false);
    }
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp).toLocaleString();
  };

  const getPostLabel = (post: CommunityPost) => {
    switch (post.type) {
      case "story":
        return "Breath Story";
      case "bridge":
        return "Yoga Bridge";
      case "reddit":
        return post.subreddit ? `From r/${post.subreddit}` : "From Reddit";
      default:
        return "Post";
    }
  };

  const getPostAuthor = (post: CommunityPost) => {
    if (post.type === "reddit") return post.author || "Redditor";
    if (post.type === "bridge") return post.who || "Someone";
    return post.name || "Anonymous";
  };

  const sortedPosts = [...posts]
    .sort((a, b) => b.timestamp - a.timestamp)
    .slice(0, 40);

  return (
    <div className="fixed inset-0 overflow-y-auto">
      {/* Background */}
      <div
        className="fixed inset-0 bg-cover bg-center"
        style={{ backgroundImage: `url(${meditationBg})` }}
      >
        <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-[hsl(var(--gradient-community-start))]/50 to-black/60" />
      </div>

      {/* Header */}
      <div className="relative z-10 p-6 flex justify-between items-center">
        <Button
          variant="ghost"
          onClick={() => navigate("/menu")}
          className="text-white hover:bg-white/10"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back
        </Button>

        <div className="flex gap-3">
          <Button
            onClick={() => setShowStoryForm(!showStoryForm)}
            className="bg-white/20 hover:bg-white/30 text-white border border-white/30"
          >
            <Plus className="mr-2 h-4 w-4" />
            Share Story
          </Button>
          <Button
            onClick={() => setShowBridgeForm(!showBridgeForm)}
            className="bg-white/20 hover:bg-white/30 text-white border border-white/30"
          >
            <Plus className="mr-2 h-4 w-4" />
            Yoga Bridge
          </Button>
          <Button
            onClick={() => void loadWall(true)}
            disabled={loading}
            className="bg-white/20 hover:bg-white/30 text-white border border-white/30"
          >
            {loading ? "Loading..." : "Refresh"}
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="relative z-10 max-w-6xl mx-auto px-6 pb-12">
        <h1 className="text-6xl font-light text-white mb-8 text-center">Community Wall</h1>

        {loadError && (
          <p className="text-center text-amber-200/90 mb-6">{loadError}</p>
        )}

        {/* Story Form */}
        {showStoryForm && (
          <div className="mb-6 bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
            <h3 className="text-2xl font-light text-white mb-4">Share Your Breath Story</h3>
            <input
              type="text"
              placeholder="Your name (optional)"
              value={storyName}
              onChange={(e) => setStoryName(e.target.value)}
              className="w-full mb-4 bg-white/10 border border-white/30 rounded-lg px-4 py-3 text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-white/50"
            />
            <textarea
              placeholder="Share how a breath changed your mood..."
              value={storyText}
              onChange={(e) => setStoryText(e.target.value)}
              maxLength={200}
              className="w-full mb-4 bg-white/10 border border-white/30 rounded-lg px-4 py-3 text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-white/50 min-h-[100px]"
            />
            <div className="flex justify-between items-center">
              <span className="text-white/60 text-sm">{storyText.length} / 200</span>
              <div className="flex gap-3">
                <Button
                  onClick={() => setShowStoryForm(false)}
                  className="bg-white/10 hover:bg-white/20 text-white"
                >
                  Cancel
                </Button>
                <Button
                  onClick={() => void submitStory()}
                  disabled={saving}
                  className="bg-white/20 hover:bg-white/30 text-white"
                >
                  {saving ? "Posting..." : "Post Story"}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Bridge Form */}
        {showBridgeForm && (
          <div className="mb-6 bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20">
            <h3 className="text-2xl font-light text-white mb-4">Log a Yoga Bridge</h3>
            <input
              type="text"
              placeholder="Who was with you? (optional)"
              value={bridgeWho}
              onChange={(e) => setBridgeWho(e.target.value)}
              className="w-full mb-4 bg-white/10 border border-white/30 rounded-lg px-4 py-3 text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-white/50"
            />
            <textarea
              placeholder="Describe the moment..."
              value={bridgeWhat}
              onChange={(e) => setBridgeWhat(e.target.value)}
              className="w-full mb-4 bg-white/10 border border-white/30 rounded-lg px-4 py-3 text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-white/50 min-h-[100px]"
            />
            <div className="flex justify-end gap-3">
              <Button
                onClick={() => setShowBridgeForm(false)}
                className="bg-white/10 hover:bg-white/20 text-white"
              >
                Cancel
              </Button>
              <Button
                onClick={() => void submitBridge()}
                disabled={saving}
                className="bg-white/20 hover:bg-white/30 text-white"
              >
                {saving ? "Posting..." : "Post Bridge"}
              </Button>
            </div>
          </div>
        )}

        {/* Posts Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {loading && sortedPosts.length === 0 ? (
            <div className="col-span-full text-center py-12">
              <p className="text-white/60 text-xl">Loading community posts…</p>
            </div>
          ) : sortedPosts.length === 0 ? (
            <div className="col-span-full text-center py-12">
              <p className="text-white/60 text-xl">
                {loadError || "No posts yet. Be the first to share!"}
              </p>
            </div>
          ) : (
            sortedPosts.map((post) => (
              <div
                key={post.id}
                className="bg-white/10 backdrop-blur-md rounded-2xl p-6 border border-white/20 hover:bg-white/15 transition-all duration-300"
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs text-[#9ba3ff] uppercase tracking-wider">
                    {getPostLabel(post)}
                  </span>
                  {post.type === "reddit" && post.upvotes && (
                    <div className="flex items-center gap-1 text-white/60 text-sm">
                      <Heart className="h-3 w-3" />
                      {post.upvotes}
                    </div>
                  )}
                </div>

                <h3 className="text-white font-semibold mb-3">{getPostAuthor(post)}</h3>

                <p className="text-white/80 text-sm mb-4 leading-relaxed whitespace-pre-wrap">
                  {post.text}
                </p>

                <div className="flex items-center justify-between text-xs text-white/50">
                  <span>{formatDate(post.timestamp)}</span>
                  {post.type === "reddit" && (
                    <span className="text-[#9ba3ff]">r/{post.subreddit}</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Decorative circles */}
      <div className="fixed top-1/4 left-1/4 w-48 h-48 rounded-full bg-white/5 animate-pulse-slow pointer-events-none" />
      <div className="fixed bottom-1/4 right-1/4 w-64 h-64 rounded-full bg-white/5 animate-pulse-slow pointer-events-none" style={{ animationDelay: '1.5s' }} />
    </div>
  );
};

export default CommunityPage;
