import {
  addDoc,
  collection,
  getDocs,
  limit,
  orderBy,
  query,
  serverTimestamp,
  type DocumentData,
} from "firebase/firestore";
import { getDb, isFirebaseConfigured } from "./firebase";

export type CommunityPostType = "story" | "bridge" | "reddit";

export interface CommunityPost {
  id: string;
  type: CommunityPostType;
  name?: string;
  who?: string;
  author?: string;
  text: string;
  timestamp: number;
  upvotes?: number;
  subreddit?: string;
}

const COLLECTION = "communityPosts";

function mapDoc(id: string, data: DocumentData): CommunityPost | null {
  const type = data.type as CommunityPostType | undefined;
  if (!type || !data.text) return null;

  const timestamp =
    typeof data.timestamp === "number"
      ? data.timestamp
      : typeof data.createdAt?.toMillis === "function"
        ? data.createdAt.toMillis()
        : Date.now();

  return {
    id,
    type,
    name: data.name,
    who: data.who,
    author: data.author,
    text: String(data.text),
    timestamp,
    upvotes: data.upvotes,
    subreddit: data.subreddit,
  };
}

/** User-created wall posts only (stories + bridges). Reddit stays API-sourced. */
export async function fetchCommunityPosts(max = 40): Promise<CommunityPost[]> {
  if (!isFirebaseConfigured()) return [];

  const q = query(
    collection(getDb(), COLLECTION),
    orderBy("timestamp", "desc"),
    limit(max)
  );
  const snap = await getDocs(q);
  return snap.docs
    .map((doc) => mapDoc(doc.id, doc.data()))
    .filter((p): p is CommunityPost => p !== null && p.type !== "reddit");
}

export async function createCommunityPost(
  post: Omit<CommunityPost, "id" | "timestamp"> & { timestamp?: number }
): Promise<CommunityPost> {
  if (!isFirebaseConfigured()) {
    throw new Error("Firebase is not configured");
  }

  const timestamp = post.timestamp ?? Date.now();
  const payload = {
    type: post.type,
    text: post.text,
    timestamp,
    createdAt: serverTimestamp(),
    ...(post.name ? { name: post.name } : {}),
    ...(post.who ? { who: post.who } : {}),
    ...(post.author ? { author: post.author } : {}),
  };

  const ref = await addDoc(collection(getDb(), COLLECTION), payload);
  return {
    id: ref.id,
    type: post.type,
    text: post.text,
    timestamp,
    name: post.name,
    who: post.who,
    author: post.author,
  };
}
