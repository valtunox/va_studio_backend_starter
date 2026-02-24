#!/usr/bin/env python3
"""
GroupNB AI HR & Recruitment Platform - FAISS Embedding Pre-computation
Pre-compute embeddings for candidates, skills, jobs using FAISS vector database.

================================================================================
USAGE COMMANDS
================================================================================

Pre-compute Embeddings:
    python scripts/precompute_embeddings_faiss.py --action precompute
    python scripts/precompute_embeddings_faiss.py --action precompute -v  # verbose

Check Statistics:
    python scripts/precompute_embeddings_faiss.py --action check

================================================================================
TRAINING COMMANDS (after embeddings are computed)
================================================================================

Train Models:
    python scripts/train_cli.py train resume_parser
    python scripts/train_cli.py train resume_parser --data app/data/resume.csv
    python scripts/train_cli.py train resume_parser --incremental  # add to existing
    python scripts/train_cli.py train job_matching --data app/data/linkdin_Job_data.csv
    python scripts/train_cli.py train salary_prediction --data app/data/training_data.csv
    python scripts/train_cli.py train candidate_ranking
    python scripts/train_cli.py train interview_scoring
    python scripts/train_cli.py train all  # train all models

Validate & Status:
    python scripts/train_cli.py validate --data app/data/resume.csv --model resume_parser
    python scripts/train_cli.py status
    python scripts/train_cli.py history

Alternative (module/scripts):
    python -m app.training.cli train resume_parser app/data/resume.csv
    scripts\\train.bat train resume_parser  # Windows
    ./scripts/train.sh train resume_parser  # Linux/Mac

================================================================================
DATA FILE STRUCTURES
================================================================================

resume.csv:
    ID,Resume_str,Resume_html,Category
    12212468,"Resume text...","<html>...</html>","IT"

01_people.csv:
    person_id,name,...

04_experience.csv:
    person_id,title,firm,location,start_date,end_date

06_skills.csv:
    skill (or person_id,skill if mapped)

02_abilities.csv:
    person_id,ability

================================================================================
COMPLETE WORKFLOW
================================================================================

1. Pre-compute embeddings first:
   python scripts/precompute_embeddings_faiss.py --action precompute

2. Validate data:
   python scripts/train_cli.py validate --data app/data/resume.csv --model resume_parser

3. Train model:
   python scripts/train_cli.py train resume_parser --data app/data/resume.csv

4. Check status:
   python scripts/train_cli.py status

================================================================================
TESTING (run from project root with PYTHONPATH set)
================================================================================

Linux/Mac:
    export PYTHONPATH="$(pwd):$PYTHONPATH"

Windows PowerShell:
    $env:PYTHONPATH = "$env:PYTHONPATH;$(Get-Location)"

Run tests:
    python -m pytest app/tests/unit/test_embedding_service.py -v
    python -m pytest app/tests/unit/test_model_trainer.py -v
    python -m pytest app/tests/unit/ -v --cov=app --cov-report=term-missing
"""

import asyncio
import argparse
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

# Add project root to path to import app modules
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent
app_dir = project_root / "app"

# Add both project root and app directory to Python path
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(app_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def simple_precompute():
    """Simple pre-computation with FAISS vector database"""
    logger.info("🚀 Starting FAISS embedding pre-computation...")
    
    try:
        # Initialize embedding service
        logger.info("🔧 Initializing embedding service...")
        
        # Import embedding service - try relative import first, then absolute
        try:
            from services.ai.ml import embedding_service
        except ImportError:
            try:
                from app.services.ai.ml import embedding_service
            except ImportError:
                # Add app directory explicitly to path
                import sys
                sys.path.insert(0, str(app_dir))
                from services.ai.ml import embedding_service
        
        embedding_success = await embedding_service.initialize()
        if not embedding_success:
            logger.error("❌ Failed to initialize embedding service")
            return False
        
        logger.info("✅ Embedding service initialized")
        
        # Process CSV files - use actual files in data directory
        data_dir = app_dir / "data"
        total_processed = 0
        start_time = datetime.now()
        
        # Load all candidate data files
        people_file = data_dir / "01_people.csv"
        experience_file = data_dir / "04_experience.csv"
        skills_file = data_dir / "06_skills.csv"
        abilities_file = data_dir / "02_abilities.csv"
        education_file = data_dir / "03_education.csv"
        
        # Load job data files
        linkedin_jobs_file = data_dir / "linkdin_Job_data.csv"
        training_data_file = data_dir / "training_data.csv"
        resume_file = data_dir / "resume.csv"
        
        # Process candidate profiles (combining people + experience + skills)
        if people_file.exists():
            logger.info("🔄 Processing candidate profiles...")
            
            # Load people data
            people_df = pd.read_csv(people_file)
            logger.info(f"📊 Loaded {len(people_df)} people records")
            
            # Load experience data
            experience_df = pd.read_csv(experience_file) if experience_file.exists() else pd.DataFrame()
            if not experience_df.empty:
                logger.info(f"📊 Loaded {len(experience_df)} experience records")
            
            # Load skills data (if it has person_id mapping, otherwise treat as general skills)
            skills_df = pd.read_csv(skills_file) if skills_file.exists() else pd.DataFrame()
            if not skills_df.empty:
                logger.info(f"📊 Loaded {len(skills_df)} skills records")
            
            # Process in batches
            batch_size = 50
            processed_count = 0
            
            for i in range(0, len(people_df), batch_size):
                batch_people = people_df.iloc[i:i+batch_size]
                
                texts = []
                content_ids = []
                metadata_list = []
                
                for idx, person_row in batch_people.iterrows():
                    person_id = person_row.get('person_id', idx)
                    name = person_row.get('name', '')
                    
                    # Build candidate profile text
                    profile_parts = []
                    
                    # Add name
                    if name:
                        profile_parts.append(f"Name: {name}")
                    
                    # Add experience
                    if not experience_df.empty:
                        person_experience = experience_df[experience_df['person_id'] == person_id]
                        if not person_experience.empty:
                            profile_parts.append("Experience:")
                            for exp_idx, exp_row in person_experience.iterrows():
                                title = exp_row.get('title', '')
                                firm = exp_row.get('firm', '')
                                location = exp_row.get('location', '')
                                start_date = exp_row.get('start_date', '')
                                end_date = exp_row.get('end_date', '')
                                exp_text = f"  - {title} at {firm}"
                                if location:
                                    exp_text += f" ({location})"
                                if start_date or end_date:
                                    exp_text += f" from {start_date} to {end_date}"
                                profile_parts.append(exp_text)
                    
                    # Add skills (if skills file has person_id, otherwise add general skills)
                    if not skills_df.empty:
                        if 'person_id' in skills_df.columns:
                            person_skills = skills_df[skills_df['person_id'] == person_id]
                            if not person_skills.empty:
                                skills_list = person_skills['skill'].tolist() if 'skill' in person_skills.columns else []
                                if skills_list:
                                    profile_parts.append(f"Skills: {', '.join(skills_list[:20])}")  # Limit to 20 skills
                        else:
                            # General skills - add a sample for diversity
                            if idx < len(skills_df):
                                sample_skills = skills_df['skill'].iloc[idx:idx+10].tolist() if 'skill' in skills_df.columns else []
                                if sample_skills:
                                    profile_parts.append(f"Skills: {', '.join(sample_skills)}")
                    
                    # Combine all parts
                    profile_text = "\n".join(profile_parts)
                    
                    if profile_text and len(profile_text.strip()) > 20:
                        texts.append(profile_text)
                        content_ids.append(f"candidate_{person_id}")
                        metadata_list.append({
                            'person_id': person_id,
                            'name': name,
                            'source': 'candidate_profile',
                            'batch': i // batch_size,
                            'row_index': idx
                        })
                
                if texts:
                    # Store embeddings using the embedding service
                    stored = await embedding_service.store_embeddings(
                        texts, "candidate", content_ids, metadata_list
                    )
                    processed_count += stored
                    
                    logger.info(f"✅ Processed batch {i//batch_size + 1}: {stored} candidate embeddings")
                
                # Small delay to prevent overwhelming
                await asyncio.sleep(0.1)
            
            logger.info(f"🎉 Completed candidate profiles: {processed_count} embeddings")
            total_processed += processed_count
        
        # Process skills as standalone embeddings (for skill-based search)
        if skills_file.exists():
            logger.info("🔄 Processing skills for skill-based search...")
            skills_df = pd.read_csv(skills_file)
            logger.info(f"📊 Loaded {len(skills_df)} skills")
            
            # Process skills in batches
            batch_size = 100
            processed_count = 0
            
            for i in range(0, len(skills_df), batch_size):
                batch_skills = skills_df.iloc[i:i+batch_size]
                
                texts = []
                content_ids = []
                metadata_list = []
                
                for idx, row in batch_skills.iterrows():
                    skill_text = str(row.get('skill', ''))
                    if skill_text and len(skill_text.strip()) > 0:
                        texts.append(f"Skill: {skill_text}")
                        content_ids.append(f"skill_{idx}")
                        metadata_list.append({
                            'skill': skill_text,
                            'source': 'skills_csv',
                            'batch': i // batch_size,
                            'row_index': idx
                        })
                
                if texts:
                    stored = await embedding_service.store_embeddings(
                        texts, "skill", content_ids, metadata_list
                    )
                    processed_count += stored
                    
                    logger.info(f"✅ Processed skills batch {i//batch_size + 1}: {stored} skill embeddings")
                
                await asyncio.sleep(0.05)
            
            logger.info(f"🎉 Completed skills: {processed_count} embeddings")
            total_processed += processed_count
        
        # Process LinkedIn job postings
        if linkedin_jobs_file.exists():
            logger.info("🔄 Processing LinkedIn job postings...")
            linkedin_df = pd.read_csv(linkedin_jobs_file)
            logger.info(f"📊 Loaded {len(linkedin_df)} LinkedIn job records")
            
            batch_size = 50
            processed_count = 0
            
            for i in range(0, len(linkedin_df), batch_size):
                batch_jobs = linkedin_df.iloc[i:i+batch_size]
                
                texts = []
                content_ids = []
                metadata_list = []
                
                for idx, job_row in batch_jobs.iterrows():
                    job_id = job_row.get('job_ID', idx)
                    job_title = job_row.get('job', '')
                    company_name = job_row.get('company_name', '')
                    location = job_row.get('location', '')
                    job_details = job_row.get('job_details', '')
                    work_type = job_row.get('work_type', '')
                    employment_type = job_row.get('full_time_remote', '')
                    
                    # Build job posting text for embedding
                    job_parts = []
                    
                    if job_title:
                        job_parts.append(f"Job Title: {job_title}")
                    
                    if company_name:
                        job_parts.append(f"Company: {company_name}")
                    
                    if location:
                        job_parts.append(f"Location: {location}")
                    
                    if work_type:
                        job_parts.append(f"Work Type: {work_type}")
                    
                    if employment_type:
                        job_parts.append(f"Employment Type: {employment_type}")
                    
                    if job_details:
                        # Limit job details to first 500 characters to avoid extremely long texts
                        truncated_details = job_details[:500] if len(str(job_details)) > 500 else job_details
                        job_parts.append(f"Job Details: {truncated_details}")
                    
                    # Combine all parts
                    job_text = "\n".join(str(part) for part in job_parts)
                    
                    if job_text and len(job_text.strip()) > 30:
                        texts.append(job_text)
                        content_ids.append(f"job_{job_id}")
                        metadata_list.append({
                            'job_id': job_id,
                            'job_title': job_title,
                            'company': company_name,
                            'location': location,
                            'source': 'linkedin_jobs',
                            'batch': i // batch_size,
                            'row_index': idx
                        })
                
                if texts:
                    # Store embeddings using the embedding service
                    stored = await embedding_service.store_embeddings(
                        texts, "job", content_ids, metadata_list
                    )
                    processed_count += stored
                    
                    logger.info(f"✅ Processed LinkedIn batch {i//batch_size + 1}: {stored} job embeddings")
                
                await asyncio.sleep(0.1)
            
            logger.info(f"🎉 Completed LinkedIn jobs: {processed_count} embeddings")
            total_processed += processed_count
        
        # Process resume.csv for resume embeddings (training data)
        if resume_file.exists():
            logger.info("🔄 Processing resume.csv for resume embeddings...")
            resume_df = pd.read_csv(resume_file)
            logger.info(f"📊 Loaded {len(resume_df)} resume records")
            
            batch_size = 50
            processed_count = 0
            
            for i in range(0, len(resume_df), batch_size):
                batch_resumes = resume_df.iloc[i:i+batch_size]
                
                texts = []
                content_ids = []
                metadata_list = []
                
                for idx, resume_row in batch_resumes.iterrows():
                    resume_id = resume_row.get('ID', idx)
                    resume_text = str(resume_row.get('Resume_str', ''))
                    category = resume_row.get('Category', 'IT')
                    
                    if resume_text and len(resume_text.strip()) > 50:
                        texts.append(resume_text)
                        content_ids.append(f"resume_{resume_id}")
                        metadata_list.append({
                            'resume_id': resume_id,
                            'category': category,
                            'source': 'resume_csv',
                            'batch': i // batch_size,
                            'row_index': idx
                        })
                
                if texts:
                    stored = await embedding_service.store_embeddings(
                        texts, "resume", content_ids, metadata_list
                    )
                    processed_count += stored
                    
                    logger.info(f"✅ Processed resume batch {i//batch_size + 1}: {stored} resume embeddings")
                
                await asyncio.sleep(0.1)
            
            logger.info(f"🎉 Completed resumes: {processed_count} embeddings")
            total_processed += processed_count
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        logger.info("🎉 Pre-computation completed!")
        logger.info(f"📊 Total embeddings processed: {total_processed}")
        logger.info(f"⏱️ Total time: {duration:.2f} seconds ({duration/60:.1f} minutes)")
        logger.info(f"⚡ Average speed: {total_processed/duration:.1f} embeddings/second")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Pre-computation failed: {e}")
        import traceback
        logger.error(f"❌ Full error: {traceback.format_exc()}")
        return False


async def check_stats():
    """Check FAISS embedding statistics"""
    logger.info("🔍 Checking FAISS embedding statistics...")
    
    try:
        # Import embedding service - try relative import first, then absolute
        try:
            from services.ai.ml import embedding_service
        except ImportError:
            try:
                from app.services.ai.ml import embedding_service
            except ImportError:
                # Add app directory explicitly to path
                import sys
                sys.path.insert(0, str(app_dir))
                from services.ai.ml import embedding_service
        
        # Initialize embedding service
        embedding_success = await embedding_service.initialize()
        if not embedding_success:
            logger.error("❌ Failed to initialize embedding service")
            return False
        
        # Get vector store stats
        stats = await embedding_service.get_vector_store_stats()
        
        logger.info(f"📊 Total vectors: {stats.get('total_vectors', 0)}")
        logger.info(f"📂 By type: {stats.get('by_type', {})}")
        logger.info(f"🔍 Total searches: {stats.get('total_searches', 0)}")
        logger.info(f"⚡ Avg search time: {stats.get('avg_search_time_ms', 0):.2f}ms")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to check stats: {e}")
        return False


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(description="FAISS embedding pre-computation")
    parser.add_argument("--action", choices=["precompute", "check"], 
                       default="precompute", help="Action to perform")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    logger.info("🎯 GroupNB AI HR & Recruitment Platform - FAISS Pre-computation")
    logger.info(f"📋 Action: {args.action}")
    
    async def run_action():
        if args.action == "check":
            success = await check_stats()
            return 0 if success else 1
            
        elif args.action == "precompute":
            success = await simple_precompute()
            return 0 if success else 1
        
        return 0
    
    # Run the async function
    try:
        exit_code = asyncio.run(run_action())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("⏹️ Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        import traceback
        logger.error(f"❌ Full error: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
