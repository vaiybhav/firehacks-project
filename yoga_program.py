"""
Yoga program/sequence management
"""
import os
import json
import random
from typing import List, Dict, Optional
import config

class YogaProgram:
    """Manages yoga programs and sequences"""
    
    def __init__(self):
        self.programs = {}
        self.load_programs()
    
    def load_programs(self):
        """Load predefined programs with smooth, practical transitions."""
        self.programs['beginner'] = {
            'name': 'Beginner Flow',
            'description': 'Floor warm-up, standing flow, and a calm finish.',
            'poses': [
                'Cat_Cow_Pose_or_Marjaryasana_',
                'Extended_Puppy_Pose_or_Uttana_Shishosana_',
                'Low_Lunge_pose_or_Anjaneyasana_',
                'Warrior_II_Pose_or_Virabhadrasana_II_',
                'Tree_Pose_or_Vrksasana_',
                'Garland_Pose_or_Malasana_',
                'Supta_Baddha_Konasana_',
                'Corpse_Pose_or_Savasana_',
            ],
            'hold_times': [12, 12, 15, 15, 15, 12, 15, 20],
        }
        
        # Short morning sequence
        self.programs['morning'] = {
            'name': 'Morning Energizer',
            'description': 'A short progressive flow from floor to standing.',
            'poses': [
                'Cat_Cow_Pose_or_Marjaryasana_',
                'Low_Lunge_pose_or_Anjaneyasana_',
                'Warrior_II_Pose_or_Virabhadrasana_II_',
                'Chair_Pose_or_Utkatasana_',
                'Tree_Pose_or_Vrksasana_',
                'Virasana_or_Vajrasana',
            ],
            'hold_times': [10, 15, 15, 12, 15, 12],
        }
        
        # Standing balance sequence
        self.programs['flexibility'] = {
            'name': 'Standing Balance',
            'description': 'Stable standing poses with sensible transitions.',
            'poses': [
                'Low_Lunge_pose_or_Anjaneyasana_',
                'Warrior_II_Pose_or_Virabhadrasana_II_',
                'Chair_Pose_or_Utkatasana_',
                'Tree_Pose_or_Vrksasana_',
            ],
            'hold_times': [15, 15, 12, 15],
        }
        
        # General full-body sequence
        self.programs['custom'] = {
            'name': 'Balanced Full-Body Flow',
            'description': 'Balanced full-body flow with a reclined finish.',
            'poses': [
                'Cat_Cow_Pose_or_Marjaryasana_',
                'Extended_Puppy_Pose_or_Uttana_Shishosana_',
                'Low_Lunge_pose_or_Anjaneyasana_',
                'Warrior_II_Pose_or_Virabhadrasana_II_',
                'Tree_Pose_or_Vrksasana_',
                'Garland_Pose_or_Malasana_',
                'Virasana_or_Vajrasana',
                'Supta_Baddha_Konasana_',
                'Corpse_Pose_or_Savasana_',
            ],
            'hold_times': [12, 12, 15, 15, 15, 12, 12, 15, 20],
        }
        
        # Comprehensive test program with all selected poses - TREE POSE FIRST
        self.programs['test_all'] = {
            'name': 'Complete Pose Test',
            'description': 'Test all selected poses - Tree Pose first!',
            'poses': [
                'Tree_Pose_or_Vrksasana_',  # TREE POSE FIRST!
                'Boat_Pose_or_Paripurna_Navasana_',
                'Bound_Angle_Pose_or_Baddha_Konasana_',
                'Cat_Cow_Pose_or_Marjaryasana_',
                'Chair_Pose_or_Utkatasana_',
                'Corpse_Pose_or_Savasana_',
                'Dolphin_Plank_Pose_or_Makara_Adho_Mukha_Svanasana_',
                'Extended_Puppy_Pose_or_Uttana_Shishosana_',
                'Extended_Revolved_Side_Angle_Pose_or_Utthita_Parsvakonasana_',
                'Four-Limbed_Staff_Pose_or_Chaturanga_Dandasana_',
                'Garland_Pose_or_Malasana_',
                'Gate_Pose_or_Parighasana_',
                'Happy_Baby_Pose_or_Ananda_Balasana_',
                'Locust_Pose_or_Salabhasana_',
                'Low_Lunge_pose_or_Anjaneyasana_',
                'Sitting pose 1 (normal)',
                'Staff_Pose_or_Dandasana_',
                'Plank_Pose_or_Kumbhakasana_',
                'Supta_Baddha_Konasana_',
                'viparita_virabhadrasana_or_reverse_warrior_pose',
                'Virasana_or_Vajrasana',
                'Warrior_I_Pose_or_Virabhadrasana_I_',
                'Warrior_II_Pose_or_Virabhadrasana_II_',
                'Wind_Relieving_pose_or_Pawanmuktasana',
            ],
            'hold_times': [15] * 24,  # 15 seconds each for testing
        }
    
    def get_program(self, program_name: str) -> Optional[Dict]:
        """Get a program by name"""
        return self.programs.get(program_name)
    
    def list_programs(self) -> List[str]:
        """List all available programs"""
        return list(self.programs.keys())
    
    def get_pose_image_path(self, pose_name: str) -> Optional[str]:
        """Get a sample image path for a pose"""
        # Try to find an image in the dataset
        for split in ['train', 'valid', 'test']:
            pose_dir = os.path.join(config.DATASET_ROOT, split, pose_name)
            if os.path.exists(pose_dir):
                # Get first image
                image_files = [f for f in os.listdir(pose_dir) 
                             if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                if image_files:
                    return os.path.join(pose_dir, image_files[0])
        return None
