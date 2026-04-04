#!/usr/bin/env python3
"""
Generate Resume CSV - Training Data Generator
===============================================

Generate resume.csv from existing people, experience, abilities, and education data.
Creates 100+ resume samples for training by combining real data with variations.

Usage:
    python scripts/database/generate_resume_csv.py
"""
import pandas as pd
import numpy as np
from pathlib import Path
import random

# Resolve project root from script location (scripts/database/)
script_dir = Path(__file__).parent
project_root = script_dir.parent.parent

# Skills pool for augmentation
SKILLS_POOL = {
    'Python Developer': ['Python', 'Django', 'Flask', 'FastAPI', 'Pandas', 'NumPy', 'TensorFlow', 'PyTorch', 'AWS', 'Docker'],
    'Database': ['SQL', 'PostgreSQL', 'MySQL', 'Oracle', 'MongoDB', 'Redis', 'Database Administration', 'PL/SQL', 'T-SQL', 'Data Modeling'],
    'Java Developer': ['Java', 'Spring Boot', 'Hibernate', 'Maven', 'Gradle', 'JUnit', 'Microservices', 'REST API', 'Kafka', 'AWS'],
    'Web Development': ['JavaScript', 'React', 'Vue.js', 'Angular', 'HTML5', 'CSS3', 'TypeScript', 'Node.js', 'Webpack', 'REST API'],
    'DevOps': ['Docker', 'Kubernetes', 'Jenkins', 'CI/CD', 'AWS', 'Azure', 'Terraform', 'Ansible', 'Linux', 'Git'],
    'Project Management': ['Agile', 'Scrum', 'JIRA', 'Confluence', 'Project Planning', 'Team Leadership', 'Stakeholder Management', 'Risk Management'],
    'Data Science': ['Python', 'R', 'Machine Learning', 'Deep Learning', 'TensorFlow', 'Pandas', 'SQL', 'Tableau', 'Statistics', 'NLP'],
    'IT': ['Technical Support', 'System Administration', 'Networking', 'Troubleshooting', 'Windows Server', 'Active Directory', 'Office 365'],
    'Cloud Engineer': ['AWS', 'Azure', 'GCP', 'CloudFormation', 'Lambda', 'EC2', 'S3', 'Kubernetes', 'Serverless', 'IAM'],
    'Mobile Developer': ['React Native', 'Flutter', 'iOS', 'Android', 'Swift', 'Kotlin', 'Mobile UI/UX', 'REST API', 'Firebase']
}

JOB_TITLES = {
    'Python Developer': ['Python Developer', 'Senior Python Developer', 'Python Engineer', 'Backend Developer', 'Software Engineer'],
    'Database': ['Database Administrator', 'DBA', 'Senior DBA', 'Database Developer', 'Data Engineer'],
    'Java Developer': ['Java Developer', 'Senior Java Developer', 'Java Engineer', 'Backend Engineer', 'Full Stack Java Developer'],
    'Web Development': ['Frontend Developer', 'Web Developer', 'UI Developer', 'UX Developer', 'Full Stack Developer'],
    'DevOps': ['DevOps Engineer', 'Site Reliability Engineer', 'Platform Engineer', 'Infrastructure Engineer', 'Cloud Engineer'],
    'Project Management': ['Project Manager', 'Scrum Master', 'Agile Coach', 'Technical Project Manager', 'Program Manager'],
    'Data Science': ['Data Scientist', 'ML Engineer', 'Data Analyst', 'AI Engineer', 'Research Scientist'],
    'IT': ['IT Support', 'System Administrator', 'IT Specialist', 'Help Desk Technician', 'IT Manager'],
    'Cloud Engineer': ['Cloud Engineer', 'AWS Engineer', 'Azure Engineer', 'Cloud Architect', 'Cloud Solutions Architect'],
    'Mobile Developer': ['Mobile Developer', 'iOS Developer', 'Android Developer', 'React Native Developer', 'Flutter Developer']
}

COMPANIES = [
    'Tech Solutions Inc.', 'Data Systems Corp.', 'Cloud Innovations', 'Digital Dynamics',
    'Software Solutions LLC', 'Enterprise Tech', 'Global IT Services', 'Innovative Systems',
    'Future Technologies', 'Smart Solutions', 'Accenture', 'IBM', 'Microsoft', 'Google',
    'Amazon', 'Meta', 'Oracle', 'Salesforce', 'Adobe', 'Cisco', 'Intel', 'HP', 'Dell'
]

LOCATIONS = [
    'New York, NY', 'San Francisco, CA', 'Seattle, WA', 'Austin, TX', 'Boston, MA',
    'Chicago, IL', 'Denver, CO', 'Atlanta, GA', 'Dallas, TX', 'Los Angeles, CA',
    'Washington, DC', 'Toronto, ON', 'Vancouver, BC', 'Remote', 'Hybrid'
]


def categorize_title(title: str) -> str:
    """Determine category from job title"""
    title_lower = title.lower()
    if 'python' in title_lower:
        return 'Python Developer'
    elif 'oracle' in title_lower or 'sql' in title_lower or 'database' in title_lower or 'dba' in title_lower:
        return 'Database'
    elif 'java' in title_lower and 'javascript' not in title_lower:
        return 'Java Developer'
    elif 'front' in title_lower or 'ui' in title_lower or 'ux' in title_lower or 'web' in title_lower or 'react' in title_lower or 'angular' in title_lower:
        return 'Web Development'
    elif 'devops' in title_lower or 'sre' in title_lower or 'infrastructure' in title_lower:
        return 'DevOps'
    elif 'scrum' in title_lower or 'project' in title_lower or 'manager' in title_lower:
        return 'Project Management'
    elif 'data' in title_lower and ('scien' in title_lower or 'analy' in title_lower or 'ml' in title_lower):
        return 'Data Science'
    elif 'cloud' in title_lower or 'aws' in title_lower or 'azure' in title_lower:
        return 'Cloud Engineer'
    elif 'mobile' in title_lower or 'ios' in title_lower or 'android' in title_lower or 'flutter' in title_lower:
        return 'Mobile Developer'
    elif 'software' in title_lower or 'engineer' in title_lower:
        return 'DevOps'
    else:
        return 'IT'


def generate_resume_text(name: str, title: str, experiences: list, education: list, skills: list, summary: str = '') -> str:
    """Generate a comprehensive resume text"""
    parts = []
    
    # Header
    parts.append(f"Name: {name}")
    parts.append(f"Title: {title}")
    
    # Summary
    if summary:
        parts.append(f"\nProfessional Summary:\n{summary}")
    
    # Experience
    if experiences:
        parts.append("\nWork Experience:")
        for exp in experiences[:5]:
            parts.append(f"  - {exp}")
    
    # Education
    if education:
        parts.append("\nEducation:")
        for edu in education[:3]:
            parts.append(f"  - {edu}")
    
    # Skills
    if skills:
        parts.append(f"\nSkills: {', '.join(skills[:15])}")
    
    return '\n'.join(parts)


def generate_resume_csv():
    data_dir = project_root / 'app' / 'data'
    
    # Load all data
    people_df = pd.read_csv(data_dir / '01_people.csv')
    experience_df = pd.read_csv(data_dir / '04_experience.csv')
    abilities_df = pd.read_csv(data_dir / '02_abilities.csv')
    education_df = pd.read_csv(data_dir / '03_education.csv')
    skills_df = pd.read_csv(data_dir / '06_skills.csv')
    
    print(f"Loaded: {len(people_df)} people, {len(experience_df)} experiences, {len(abilities_df)} abilities, {len(education_df)} education, {len(skills_df)} skills")
    
    resumes = []
    resume_id = 1
    
    # === Part 1: Create resumes from existing people data ===
    for _, person in people_df.iterrows():
        pid = person['person_id']
        name = str(person['name'])
        
        # Get experiences
        exp = experience_df[experience_df['person_id'] == pid]
        experiences = []
        if not exp.empty:
            for _, e in exp.iterrows():
                loc = e.get('location', '') if pd.notna(e.get('location', '')) else ''
                title = e.get('title', '')
                firm = e.get('firm', '')
                exp_str = f"{title} at {firm}"
                if loc:
                    exp_str += f" ({loc})"
                experiences.append(exp_str)
        
        # Get abilities
        abils = abilities_df[abilities_df['person_id'] == pid]
        skills = abils['ability'].tolist()[:15] if not abils.empty else []
        
        # Get education
        edu = education_df[education_df['person_id'] == pid]
        education = []
        if not edu.empty:
            for _, e in edu.iterrows():
                inst = e.get('institution', '') if pd.notna(e.get('institution', '')) else ''
                prog = e.get('program', '') if pd.notna(e.get('program', '')) else ''
                if inst or prog:
                    education.append(f"{prog} at {inst}".strip())
        
        # Determine category and add category-specific skills
        category = categorize_title(name)
        if category in SKILLS_POOL and len(skills) < 5:
            skills.extend(random.sample(SKILLS_POOL[category], min(5, len(SKILLS_POOL[category]))))
        
        # Build resume
        resume_str = generate_resume_text(name, name, experiences, education, skills)
        
        if len(resume_str) > 100:
            resumes.append({
                'ID': resume_id,
                'Resume_str': resume_str,
                'Resume_html': f'<html><body><pre>{resume_str}</pre></body></html>',
                'Category': category
            })
            resume_id += 1
    
    print(f"Generated {len(resumes)} resumes from people data")
    
    # === Part 2: Create resumes from experience data (unique person_ids not in people) ===
    exp_person_ids = experience_df['person_id'].unique()
    people_ids = set(people_df['person_id'].tolist())
    new_person_ids = [pid for pid in exp_person_ids if pid not in people_ids]
    
    for pid in new_person_ids[:50]:  # Limit to 50 more
        exp = experience_df[experience_df['person_id'] == pid]
        if exp.empty:
            continue
        
        # Use first experience title as name
        first_exp = exp.iloc[0]
        name = first_exp.get('title', 'Professional')
        
        experiences = []
        for _, e in exp.iterrows():
            loc = e.get('location', '') if pd.notna(e.get('location', '')) else ''
            title = e.get('title', '')
            firm = e.get('firm', '')
            exp_str = f"{title} at {firm}"
            if loc:
                exp_str += f" ({loc})"
            experiences.append(exp_str)
        
        # Get education
        edu = education_df[education_df['person_id'] == pid]
        education = []
        if not edu.empty:
            for _, e in edu.iterrows():
                inst = e.get('institution', '') if pd.notna(e.get('institution', '')) else ''
                prog = e.get('program', '') if pd.notna(e.get('program', '')) else ''
                if inst or prog:
                    education.append(f"{prog} at {inst}".strip())
        
        category = categorize_title(name)
        pool = SKILLS_POOL.get(category, SKILLS_POOL['IT'])
        skills = random.sample(pool, min(8, len(pool)))
        
        resume_str = generate_resume_text(name, name, experiences, education, skills)
        
        if len(resume_str) > 100:
            resumes.append({
                'ID': resume_id,
                'Resume_str': resume_str,
                'Resume_html': f'<html><body><pre>{resume_str}</pre></body></html>',
                'Category': category
            })
            resume_id += 1
    
    print(f"Total after experience data: {len(resumes)} resumes")
    
    # === Part 3: Generate synthetic resumes to reach 100+ ===
    target_count = 120
    categories = list(SKILLS_POOL.keys())
    
    while len(resumes) < target_count:
        category = random.choice(categories)
        
        # Generate random name
        first_names = ['John', 'Jane', 'Michael', 'Sarah', 'David', 'Emily', 'Robert', 'Lisa', 'James', 'Jennifer', 'Alex', 'Chris', 'Sam', 'Jordan', 'Taylor']
        last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis', 'Rodriguez', 'Martinez', 'Chen', 'Lee', 'Patel', 'Kim', 'Singh']
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        
        # Generate title
        title = random.choice(JOB_TITLES.get(category, JOB_TITLES['IT']))
        
        # Generate experiences
        num_experiences = random.randint(2, 5)
        experiences = []
        years = list(range(2015, 2025))
        random.shuffle(years)
        for i in range(num_experiences):
            exp_title = random.choice(JOB_TITLES.get(category, JOB_TITLES['IT']))
            company = random.choice(COMPANIES)
            location = random.choice(LOCATIONS)
            experiences.append(f"{exp_title} at {company} ({location})")
        
        # Generate education
        degrees = ['Bachelor of Science', 'Master of Science', 'Bachelor of Arts', 'MBA', 'PhD']
        fields = ['Computer Science', 'Information Technology', 'Software Engineering', 'Data Science', 'Business Administration']
        universities = ['MIT', 'Stanford University', 'UC Berkeley', 'Carnegie Mellon', 'Georgia Tech', 'University of Texas', 'Columbia University', 'NYU']
        education = [f"{random.choice(degrees)} in {random.choice(fields)} at {random.choice(universities)}"]
        
        # Generate skills
        skills = random.sample(SKILLS_POOL.get(category, SKILLS_POOL['IT']), min(8, len(SKILLS_POOL.get(category, SKILLS_POOL['IT']))))
        # Add some cross-category skills
        other_category = random.choice([c for c in categories if c != category])
        skills.extend(random.sample(SKILLS_POOL.get(other_category, []), 2))
        
        # Generate summary
        summaries = [
            f"Experienced {title} with {random.randint(3, 15)} years of expertise in {', '.join(skills[:3])}.",
            f"Results-driven professional specializing in {category} solutions and team leadership.",
            f"Passionate {title} dedicated to delivering high-quality software solutions.",
            f"Skilled {category} specialist with proven track record in enterprise environments."
        ]
        summary = random.choice(summaries)
        
        resume_str = generate_resume_text(name, title, experiences, education, skills, summary)
        
        resumes.append({
            'ID': resume_id,
            'Resume_str': resume_str,
            'Resume_html': f'<html><body><pre>{resume_str}</pre></body></html>',
            'Category': category
        })
        resume_id += 1
    
    print(f"Total after synthetic data: {len(resumes)} resumes")
    
    # Save
    resume_df = pd.DataFrame(resumes)
    output_path = data_dir / 'resume.csv'
    resume_df.to_csv(output_path, index=False)
    
    print(f"\n[OK] Created {output_path} with {len(resume_df)} records")
    print(f"\nCategories breakdown:")
    for cat, count in resume_df['Category'].value_counts().items():
        print(f"   {cat}: {count}")


if __name__ == '__main__':
    generate_resume_csv()
