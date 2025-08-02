# ml_reengagement_system.py - Fixed Version with Proper Imports

import os
import json
import requests
from datetime import datetime, timedelta
from collections import defaultdict
# Remove schedule import for now - we'll add it later
# import schedule
import time

# Import Firebase
from firebase_admin_init import db

class MLReengagementEngine:
    """Weekly ML analysis system using Tiny Llama for playlist optimization"""
    
    def __init__(self):
        self.llm_endpoint = os.getenv("TINYLLAMA_ENDPOINT", "http://localhost:11434/api/generate")
        self.model_name = "tinyllama:1.1b"
        self.analysis_collection = "ml_analysis"
        self.recommendations_collection = "weekly_recommendations"
    
    def collect_weekly_data(self):
        """Collect and aggregate ML data from the past week"""
        print("📊 Collecting weekly ML data...")
        
        week_ago = datetime.now() - timedelta(days=7)
        week_ago_iso = week_ago.isoformat()
        
        # Collect user interactions
        interactions = []
        try:
            interactions_ref = db.collection("interactions").where("timestamp", ">=", week_ago)
            for doc in interactions_ref.stream():
                interactions.append(doc.to_dict())
        except Exception as e:
            print(f"⚠️ No interactions found: {e}")
        
        # Collect ML feedback
        feedback = []
        try:
            feedback_ref = db.collection("ml_feedback").where("timestamp", ">=", week_ago)
            for doc in feedback_ref.stream():
                feedback.append(doc.to_dict())
        except Exception as e:
            print(f"⚠️ No feedback found: {e}")
        
        # Collect cache data (popular tracks)
        cache_data = []
        try:
            cache_ref = db.collection("track_cache").where("last_accessed", ">=", week_ago_iso)
            for doc in cache_ref.stream():
                cache_data.append(doc.to_dict())
        except Exception as e:
            print(f"⚠️ No cache data found: {e}")
        
        # Aggregate data
        aggregated_data = {
            "week_start": week_ago.isoformat(),
            "week_end": datetime.now().isoformat(),
            "total_playlists_created": len([i for i in interactions if i.get("event_type") == "built_playlist"]),
            "total_user_feedback": len(feedback),
            "popular_tracks": sorted(cache_data, key=lambda x: x.get("hit_count", 0), reverse=True)[:50],
            "genre_popularity": self._analyze_genre_trends(interactions),
            "mood_patterns": self._analyze_mood_patterns(interactions),
            "user_engagement": self._analyze_user_engagement(interactions, feedback),
            "playlist_success_metrics": self._analyze_playlist_success(feedback)
        }
        
        print(f"📊 Collected data: {aggregated_data['total_playlists_created']} playlists, {len(feedback)} feedback items")
        return aggregated_data
    
    def _analyze_genre_trends(self, interactions):
        """Analyze genre popularity trends"""
        genre_counts = defaultdict(int)
        for interaction in interactions:
            if interaction.get("event_type") == "built_playlist":
                genres = interaction.get("data", {}).get("genres", [])
                for genre in genres:
                    genre_counts[genre] += 1
        
        return dict(sorted(genre_counts.items(), key=lambda x: x[1], reverse=True))
    
    def _analyze_mood_patterns(self, interactions):
        """Analyze mood tag patterns"""
        mood_counts = defaultdict(int)
        for interaction in interactions:
            if interaction.get("event_type") == "built_playlist":
                moods = interaction.get("data", {}).get("mood_tags", [])
                for mood in moods:
                    mood_counts[mood] += 1
        
        return dict(sorted(mood_counts.items(), key=lambda x: x[1], reverse=True))
    
    def _analyze_user_engagement(self, interactions, feedback):
        """Analyze user engagement patterns"""
        user_stats = defaultdict(lambda: {"playlists": 0, "feedback": 0})
        
        for interaction in interactions:
            user_id = interaction.get("user_id", "anonymous")
            if interaction.get("event_type") == "built_playlist":
                user_stats[user_id]["playlists"] += 1
        
        for fb in feedback:
            user_id = fb.get("user_id", "anonymous")
            user_stats[user_id]["feedback"] += 1
        
        # Calculate engagement metrics
        active_users = len([u for u, stats in user_stats.items() if stats["playlists"] > 0])
        avg_playlists = sum(stats["playlists"] for stats in user_stats.values()) / max(active_users, 1)
        
        return {
            "active_users": active_users,
            "average_playlists_per_user": round(avg_playlists, 2),
            "feedback_rate": len(feedback) / max(sum(stats["playlists"] for stats in user_stats.values()), 1)
        }
    
    def _analyze_playlist_success(self, feedback):
        """Analyze playlist success metrics"""
        if not feedback:
            return {"average_rating": 0, "success_rate": 0}
        
        ratings = [fb.get("rating", 3) for fb in feedback if "rating" in fb]
        positive_feedback = len([fb for fb in feedback if fb.get("feedback_type") == "positive"])
        
        return {
            "average_rating": sum(ratings) / len(ratings) if ratings else 0,
            "success_rate": positive_feedback / len(feedback) if feedback else 0,
            "total_feedback_items": len(feedback)
        }
    
    def query_tiny_llama(self, prompt, context_data):
        """Query Tiny Llama with weekly data analysis"""
        print(f"🤖 Querying Tiny Llama for insights...")
        
        # Prepare context for the LLM
        context = f"""
        Weekly Music Platform Analysis:
        
        Total Playlists Created: {context_data.get('total_playlists_created', 0)}
        User Feedback Items: {context_data.get('total_user_feedback', 0)}
        
        Top Genres: {list(context_data.get('genre_popularity', {}).keys())[:5]}
        Top Moods: {list(context_data.get('mood_patterns', {}).keys())[:5]}
        
        Engagement Metrics:
        - Active Users: {context_data.get('user_engagement', {}).get('active_users', 0)}
        - Average Rating: {context_data.get('playlist_success_metrics', {}).get('average_rating', 0):.1f}/5
        - Success Rate: {context_data.get('playlist_success_metrics', {}).get('success_rate', 0):.1%}
        
        Popular Tracks This Week:
        {chr(10).join([f"- {track.get('artist', 'Unknown')} - {track.get('track', 'Unknown')} (hits: {track.get('hit_count', 0)})" 
                      for track in context_data.get('popular_tracks', [])[:10]])}
        """
        
        full_prompt = f"{context}\n\nQuestion: {prompt}\n\nResponse:"
        
        payload = {
            "model": self.model_name,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "max_tokens": 500
            }
        }
        
        try:
            response = requests.post(self.llm_endpoint, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "No response from model")
            else:
                print(f"❌ LLM API error: {response.status_code}")
                return f"Fallback recommendation based on data analysis."
        except Exception as e:
            print(f"❌ LLM query error: {e}")
            return f"Unable to connect to LLM. Using fallback analysis."
    
    def generate_recommendations(self, weekly_data):
        """Generate personalized recommendations using Tiny Llama"""
        print("🎯 Generating ML-powered recommendations...")
        
        recommendations = {}
        
        # 1. Genre diversification recommendations
        genre_prompt = """Based on the genre popularity data, what 3 new or underused genres should we promote to users this week to increase musical diversity? Consider genres that might complement the popular ones."""
        
        genre_rec = self.query_tiny_llama(genre_prompt, weekly_data)
        recommendations["genre_diversification"] = genre_rec
        
        # 2. Mood-based playlist suggestions
        mood_prompt = """Based on the mood patterns, suggest 5 specific playlist themes or mood combinations that could increase user engagement. Focus on moods that are trending or underutilized."""
        
        mood_rec = self.query_tiny_llama(mood_prompt, weekly_data)
        recommendations["mood_suggestions"] = mood_rec
        
        # 3. Track replacement suggestions
        popular_tracks = weekly_data.get('popular_tracks', [])[:20]
        if popular_tracks:
            tracks_prompt = f"""Based on these popular tracks, suggest 10 similar but lesser-known tracks that could be recommended to users for playlist enhancement. Focus on discovering hidden gems in similar styles."""
            
            track_rec = self.query_tiny_llama(tracks_prompt, weekly_data)
            recommendations["track_discoveries"] = track_rec
        
        # 4. User re-engagement strategies
        engagement_data = weekly_data.get('user_engagement', {})
        success_data = weekly_data.get('playlist_success_metrics', {})
        
        engagement_prompt = f"""Based on {engagement_data.get('active_users', 0)} active users with an average rating of {success_data.get('average_rating', 0):.1f}/5, suggest 3 specific strategies to re-engage users and improve playlist satisfaction."""
        
        engagement_rec = self.query_tiny_llama(engagement_prompt, weekly_data)
        recommendations["reengagement_strategies"] = engagement_rec
        
        return recommendations
    
    def create_user_notifications(self, recommendations, weekly_data):
        """Create personalized user notifications based on ML insights"""
        notifications = []
        
        # Get active users from the past week
        week_ago = datetime.now() - timedelta(days=7)
        active_users = set()
        
        try:
            interactions_ref = db.collection("interactions").where("timestamp", ">=", week_ago)
            for doc in interactions_ref.stream():
                interaction = doc.to_dict()
                if interaction.get("event_type") == "built_playlist":
                    active_users.add(interaction.get("user_id"))
        except Exception as e:
            print(f"⚠️ No active users found: {e}")
        
        print(f"📨 Creating notifications for {len(active_users)} active users...")
        
        for user_id in active_users:
            if user_id and user_id != "anonymous":
                # Personalized notification based on user's recent activity
                user_notification = {
                    "user_id": user_id,
                    "type": "weekly_recommendations",
                    "title": "🎵 New Music Discoveries This Week!",
                    "message": "Based on your listening patterns and community trends, we have some exciting new tracks and playlist ideas for you.",
                    "recommendations": {
                        "suggested_genres": str(recommendations.get("genre_diversification", ""))[:200],
                        "playlist_ideas": str(recommendations.get("mood_suggestions", ""))[:200],
                        "track_discoveries": str(recommendations.get("track_discoveries", ""))[:300]
                    },
                    "created_at": datetime.now().isoformat(),
                    "expires_at": (datetime.now() + timedelta(days=7)).isoformat(),
                    "status": "pending"
                }
                
                notifications.append(user_notification)
        
        return notifications
    
    def store_analysis_results(self, weekly_data, recommendations, notifications):
        """Store ML analysis results in Firebase"""
        print("💾 Storing ML analysis results...")
        
        analysis_doc = {
            "analysis_date": datetime.now().isoformat(),
            "week_analyzed": {
                "start": weekly_data["week_start"],
                "end": weekly_data["week_end"]
            },
            "raw_data": weekly_data,
            "ml_recommendations": recommendations,
            "notifications_created": len(notifications),
            "analysis_version": "v1.0"
        }
        
        # Store main analysis
        db.collection(self.analysis_collection).add(analysis_doc)
        
        # Store individual notifications
        for notification in notifications:
            db.collection(self.recommendations_collection).add(notification)
        
        print(f"✅ Stored analysis and {len(notifications)} user notifications")
    
    def run_weekly_analysis(self):
        """Main function to run complete weekly analysis"""
        print("🚀 Starting weekly ML analysis and re-engagement system...")
        
        try:
            # Step 1: Collect data
            weekly_data = self.collect_weekly_data()
            
            # Step 2: Generate ML recommendations
            recommendations = self.generate_recommendations(weekly_data)
            
            # Step 3: Create user notifications
            notifications = self.create_user_notifications(recommendations, weekly_data)
            
            # Step 4: Store results
            self.store_analysis_results(weekly_data, recommendations, notifications)
            
            print("✅ Weekly ML analysis completed successfully!")
            
            # Return summary for monitoring
            return {
                "status": "success",
                "playlists_analyzed": weekly_data.get("total_playlists_created", 0),
                "users_notified": len(notifications),
                "top_genre": list(weekly_data.get("genre_popularity", {}).keys())[0] if weekly_data.get("genre_popularity") else "none",
                "engagement_score": weekly_data.get("playlist_success_metrics", {}).get("average_rating", 0)
            }
            
        except Exception as e:
            print(f"❌ Weekly analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e)}

# Test function if run directly
if __name__ == "__main__":
    print("🧪 Testing ML Reengagement Engine...")
    ml_engine = MLReengagementEngine()
    result = ml_engine.run_weekly_analysis()
    print(f"Test result: {result}")