# -*- coding: utf-8 -*-
"""
Created on Sat Aug  2 20:36:54 2025

@author: peace
"""

#!/usr/bin/env python3
"""
Simplified Medical Document Redaction System
Reliable detection with straightforward patterns
"""

import re
import sys
import os
from typing import Dict, List, Tuple, Optional

try:
    from presidio_analyzer import AnalyzerEngine
    PRESIDIO_AVAILABLE = True
except ImportError:
    PRESIDIO_AVAILABLE = False

# Expanded pharmaceutical and medical terms
PHARMACEUTICAL_NAMES = [
    # Original list
    'acetaminophen', 'aspirin', 'ibuprofen', 'tylenol', 'advil', 'albuterol',
    'lisinopril', 'metformin', 'atorvastatin', 'amlodipine', 'metoprolol',
    'hydrochlorothiazide', 'simvastatin', 'losartan', 'omeprazole', 'gabapentin',
    'levothyroxine', 'furosemide', 'prednisone', 'sumatriptan', 'topiramate',
    'warfarin', 'insulin', 'morphine', 'oxycodone', 'hydrocodone', 'fentanyl',
    
    # Medical device and surgical terms
    'monosyn', 'suture', 'surgical', 'catheter', 'stent', 'implant', 'prosthetic',
    'device', 'needle', 'syringe', 'bandage', 'gauze', 'surgical', 'medical',
    
    # Additional common drugs
    'amoxicillin', 'azithromycin', 'ciprofloxacin', 'doxycycline', 'penicillin',
    'cephalexin', 'clindamycin', 'metronidazole', 'trimethoprim', 'sulfa'
]

MANUFACTURERS = [
    'abbott', 'baxter', 'medtronic', 'johnson & johnson', 'pfizer', 'novartis',
    'b. braun', 'boston scientific', 'smith & nephew', 'stryker', 'zimmer',
    'intuitive surgical', 'edwards lifesciences', 'cardinal health'
]

# Common false positives to avoid
FALSE_POSITIVES = {
    # Articles and basic words
    'a', 'an', 'the', 'and', 'or', 'but', 'may', 'will', 'can', 'could',
    'would', 'should', 'must', 'with', 'at', 'to', 'for', 'of', 'in', 'on',
    'no', 'yes', 'not', 'all', 'any', 'some', 'each', 'every', 'this',
    'that', 'these', 'those', 'his', 'her', 'their', 'its', 'our', 'your',
    
    # Common prepositions and connectors
    'be', 'is', 'was', 'were', 'are', 'been', 'being', 'have', 'has', 'had',
    'do', 'does', 'did', 'get', 'got', 'go', 'went', 'come', 'came', 'see',
    'saw', 'know', 'knew', 'think', 'thought', 'say', 'said', 'tell', 'told',
    
    # Medical context words that are never PII
    'if', 'when', 'where', 'how', 'why', 'what', 'who', 'which', 'then',
    'now', 'here', 'there', 'up', 'down', 'out', 'over', 'under', 'through',
    'between', 'among', 'during', 'before', 'after', 'since', 'until',
    'from', 'into', 'onto', 'upon', 'about', 'above', 'below', 'beside',
    'beyond', 'within', 'without', 'toward', 'towards', 'across', 'around',
    
    # Single letters and short words
    'i', 'we', 'he', 'she', 'it', 'they', 'me', 'us', 'him', 'them',
    'my', 'our', 'one', 'two', 'ten', 'old', 'new', 'big', 'small',
    
    # Additional common words and medical terms that shouldn't be redacted
    'per', 'via', 'plus', 'minus', 'times', 'versus', 'vs', 'etc', 'ie', 'eg',
    'so', 'as', 'by', 'off', 'nor', 'yet', 'else', 'both', 'either',
    'neither', 'such', 'same', 'other', 'another', 'much', 'many', 'more',
    'most', 'less', 'few', 'little', 'own', 'only', 'just', 'even', 'also',
    'too', 'very', 'quite', 'rather', 'still', 'already', 'almost', 'enough',
    'needle', 'thread', 'package', 'sealed', 'otherwise', 'intact', 'functional',
    'appeared', 'closed', 'involvement', 'detached', 'reported', 'issue', 'client',
    'patient', 'doctor', 'nurse', 'hospital', 'medical', 'form', 'fda'
}

# Profanity list for redaction
PROFANITY_WORDS = {
    'damn', 'hell', 'shit', 'fuck', 'bitch', 'ass', 'crap', 'piss', 'bastard',
    'asshole', 'dickhead', 'motherfucker', 'goddamn', 'bloody', 'cocksucker'
}

class SimplifiedRedactionEngine:
    def __init__(self, debug=False):
        self.debug = debug
        self.presidio_analyzer = None
        
        if PRESIDIO_AVAILABLE:
            try:
                self.presidio_analyzer = AnalyzerEngine()
                self._debug_print("Presidio initialized")
            except Exception as e:
                self._debug_print(f"Presidio initialization failed: {e}")
    
    def _debug_print(self, message: str):
        if self.debug:
            print(f"DEBUG: {message}")
    
    def _is_false_positive(self, word: str) -> bool:
        """Check if word is a false positive"""
        word_lower = word.lower().strip()
        
        # Known false positives
        if word_lower in FALSE_POSITIVES:
            return True
        
        # Too short
        if len(word_lower) <= 2:
            return True
        
        # Single letters or very short acronyms
        if len(word) <= 3 and word.isupper():
            return True
        
        return False
    
    def detect_names(self, text: str) -> List[Dict]:
        """Detect person names with simple, reliable patterns"""
        findings = []
        
        patterns = [
            # Dr. + Name patterns
            (r'\bDr\.?\s+([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,})', 0.95),
            (r'\bDoctor\s+([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,})', 0.95),
            
            # Reporter names (with context)
            (r'\b(?:Reporter|Reported\s+by|Contact)[-:\s]+([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,})', 0.9),
            
            # Simple two-word names (first + last)
            (r'\b([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,})\b', 0.8),
            
            # Three-word names (first + middle + last)
            (r'\b([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,})\b', 0.85),
        ]
        
        for pattern, confidence in patterns:
            for match in re.finditer(pattern, text):
                name = match.group(1) if match.groups() else match.group()
                
                # Skip if any word is a false positive
                if any(self._is_false_positive(word) for word in name.split()):
                    continue
                
                findings.append({
                    'type': 'NAME',
                    'original': name,
                    'start': match.start(1) if match.groups() else match.start(),
                    'end': match.end(1) if match.groups() else match.end(),
                    'confidence': confidence,
                    'method': 'name_pattern'
                })
        
        return findings
    
    def detect_profanity(self, text: str) -> List[Dict]:
        """Detect profanity for redaction"""
        findings = []
        
        for word in PROFANITY_WORDS:
            pattern = rf'\b{re.escape(word)}\b'
            for match in re.finditer(pattern, text, re.IGNORECASE):
                detected_text = match.group()
                
                # Check false positives
                if self._is_false_positive(detected_text):
                    continue
                
                findings.append({
                    'type': 'PROFANITY',
                    'original': detected_text,
                    'start': match.start(),
                    'end': match.end(),
                    'confidence': 0.99,
                    'method': 'profanity_list'
                })
        
        return findings
    
    def detect_financial_info(self, text: str) -> List[Dict]:
        """Detect commercial/financial information"""
        findings = []
        
        patterns = [
            # Currency amounts
            (r'\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)', 0.85, 'FINANCIAL'),
            (r'\b(\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*dollars?)\b', 0.85, 'FINANCIAL'),
            
            # Financial terms with amounts
            (r'\b(?:cost|price|revenue|profit|loss|expense|budget|salary|wage)[-:\s]*\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', 0.9, 'FINANCIAL'),
            
            # Contract values
            (r'\b(?:contract|agreement)\s+(?:value|amount)[-:\s]*\$?\s*(\d+(?:,\d{3})*)', 0.9, 'FINANCIAL'),
            
            # Commercial terms
            (r'\b(proprietary\s+formula)\b', 0.8, 'COMMERCIAL'),
            (r'\b(trade\s+secret)\b', 0.9, 'COMMERCIAL'),
            (r'\b(confidential\s+manufacturing)\b', 0.85, 'COMMERCIAL'),
        ]
        
        for pattern, confidence, detection_type in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                amount = match.group(1) if match.groups() else match.group()
                
                # Check false positives
                if self._is_false_positive(amount):
                    continue
                
                findings.append({
                    'type': detection_type,
                    'original': amount,
                    'start': match.start(1) if match.groups() else match.start(),
                    'end': match.end(1) if match.groups() else match.end(),
                    'confidence': confidence,
                    'method': 'financial_pattern'
                })
        
        return findings
    
    def detect_locations(self, text: str) -> List[Dict]:
        """Detect cities, states, addresses, and facilities"""
        findings = []
        
        patterns = [
            # Facility names
            (r'\b([A-Z][a-z]{2,}\s+(?:Hospital|Medical\s+Center|Clinic|Health\s+Center|Healthcare|Medical\s+Group))\b', 0.9, 'FACILITY'),
            (r'\b([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\s+(?:Hospital|Medical\s+Center|Clinic))\b', 0.9, 'FACILITY'),
            
            # City, State patterns
            (r'\b([A-Z][a-z]{2,},\s*[A-Z][a-z]{2,})\b', 0.85, 'LOCATION'),
            (r'\b([A-Z][a-z]{2,},\s*[A-Z]{2})\b', 0.9, 'LOCATION'),
            
            # Full addresses
            (r'\b(\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd))', 0.9, 'ADDRESS'),
            
            # ZIP codes
            (r'\b(\d{5}(?:-\d{4})?)\b', 0.85, 'ZIP'),
            
            # State + ZIP combinations
            (r'\b([A-Z]{2}\s+\d{5}(?:-\d{4})?)\b', 0.9, 'ADDRESS'),
        ]
        
        for pattern, confidence, detection_type in patterns:
            for match in re.finditer(pattern, text):
                location = match.group(1)
                
                # Check false positives
                if self._is_false_positive(location):
                    continue
                
                findings.append({
                    'type': detection_type,
                    'original': location,
                    'start': match.start(1),
                    'end': match.end(1),
                    'confidence': confidence,
                    'method': 'location_pattern'
                })
        
        return findings
    
    def detect_contact_info(self, text: str) -> List[Dict]:
        """Detect phones, emails, etc."""
        findings = []
        
        patterns = [
            # Phone numbers
            (r'\b(\(\d{3}\)\s*\d{3}[-.\s]*\d{4})\b', 0.95, 'PHONE'),
            (r'\b(\d{3}[-.\s]*\d{3}[-.\s]*\d{4})\b', 0.9, 'PHONE'),
            
            # Email addresses
            (r'\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b', 0.98, 'EMAIL'),
            
            # Social Security Numbers
            (r'\b(\d{3}-\d{2}-\d{4})\b', 0.95, 'SSN'),
        ]
        
        for pattern, confidence, detection_type in patterns:
            for match in re.finditer(pattern, text):
                detected_text = match.group(1)
                
                # Check false positives
                if self._is_false_positive(detected_text):
                    continue
                
                findings.append({
                    'type': detection_type,
                    'original': detected_text,
                    'start': match.start(1),
                    'end': match.end(1),
                    'confidence': confidence,
                    'method': 'contact_pattern'
                })
        
        return findings
    
    def detect_dates(self, text: str) -> List[Dict]:
        """Detect various date formats"""
        findings = []
        
        patterns = [
            # MM/DD/YYYY, MM-DD-YYYY
            (r'\b(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b', 0.85),
            
            # ISO dates (YYYY-MM-DD)
            (r'\b(\d{4}-\d{1,2}-\d{1,2})\b', 0.9),
            
            # Month DD, YYYY
            (r'\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b', 0.9),
            
            # Abbreviated months
            (r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[-.\s]+\d{1,2}[-.\s]+\d{2,4})\b', 0.85),
        ]
        
        for pattern, confidence in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                date_str = match.group(1)
                
                # Check false positives
                if self._is_false_positive(date_str):
                    continue
                
                # Basic validation for MM/DD/YYYY format
                if '/' in date_str or '-' in date_str:
                    parts = re.split(r'[-/]', date_str)
                    if len(parts) == 3:
                        try:
                            if len(parts[0]) <= 2:  # MM/DD/YYYY format
                                month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
                                if month > 12 or day > 31 or year < 1900 or year > 2030:
                                    continue
                        except ValueError:
                            continue
                
                findings.append({
                    'type': 'DATE',
                    'original': date_str,
                    'start': match.start(1),
                    'end': match.end(1),
                    'confidence': confidence,
                    'method': 'date_pattern'
                })
        
        return findings
    
    def detect_medical_ids(self, text: str) -> List[Dict]:
        """Detect medical record numbers and IDs"""
        findings = []
        
        patterns = [
            # Medical Record Numbers
            (r'\b(MRN[-:\s]*[A-Z0-9-]{5,})\b', 0.95, 'MEDICAL_ID'),
            (r'\b(Medical\s+Record\s+Number[-:\s]*[A-Z0-9-]{5,})\b', 0.95, 'MEDICAL_ID'),
            
            # Patient IDs
            (r'\b(Patient\s+ID[-:\s]*[A-Z0-9-]{5,})\b', 0.9, 'MEDICAL_ID'),
            
            # Generic ID patterns (more conservative)
            (r'\b([A-Z]{2,3}-\d{6,})\b', 0.8, 'ID'),
            (r'\b(\d{8,12})\b', 0.7, 'ID'),  # Long number sequences
        ]
        
        for pattern, confidence, detection_type in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                detected_text = match.group(1)
                
                # Check false positives
                if self._is_false_positive(detected_text):
                    continue
                
                findings.append({
                    'type': detection_type,
                    'original': detected_text,
                    'start': match.start(1),
                    'end': match.end(1),
                    'confidence': confidence,
                    'method': 'medical_id_pattern'
                })
        
        return findings
    
    def detect_pharmaceuticals(self, text: str) -> List[Dict]:
        """Detect pharmaceutical names and medical devices"""
        findings = []
        
        # Known pharmaceuticals (exact match)
        for drug in PHARMACEUTICAL_NAMES:
            pattern = rf'\b{re.escape(drug)}\b'
            for match in re.finditer(pattern, text, re.IGNORECASE):
                detected_text = match.group()
                
                # Check false positives
                if self._is_false_positive(detected_text):
                    continue
                
                findings.append({
                    'type': 'PHARMACEUTICAL',
                    'original': detected_text,
                    'start': match.start(),
                    'end': match.end(),
                    'confidence': 0.9,
                    'method': 'known_pharmaceutical'
                })
        
        # Drug dosage patterns
        dosage_patterns = [
            (r'\b([A-Za-z]+\s+\d+\s?(?:mg|ml|mcg|g|units?|cc))\b', 0.8),
            (r'\b(\d+\s?(?:mg|ml|mcg|g|units?|cc)\s+of\s+[A-Za-z]+)\b', 0.8),
        ]
        
        for pattern, confidence in dosage_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                detected_text = match.group(1)
                
                # Check false positives
                if self._is_false_positive(detected_text):
                    continue
                
                findings.append({
                    'type': 'PHARMACEUTICAL',
                    'original': detected_text,
                    'start': match.start(1),
                    'end': match.end(1),
                    'confidence': confidence,
                    'method': 'dosage_pattern'
                })
        
        return findings
    
    def detect_manufacturing_info(self, text: str) -> List[Dict]:
        """Detect manufacturing numbers, lot numbers, serial numbers, transmitter/analyzer IDs"""
        findings = []
        
        patterns = [
            # Serial/Model/Lot numbers with labels
            (r'\b(?:Serial|SN|S/N|Model|Part|P/N|Lot|Batch)[-:\s]*([A-Z0-9-]{4,})\b', 0.9, 'MANUFACTURING_NUMBER'),
            
            # Transmitter and Analyzer numbers (FDA specific)
            (r'\b(?:Transmitter|Analyzer)[-:\s]*(?:Number|#|ID)[-:\s]*([A-Z0-9-]{4,})\b', 0.95, 'TRANSMITTER_ANALYZER'),
            (r'\b(TM[-]?\d{6,})\b', 0.9, 'TRANSMITTER_ANALYZER'),
            (r'\b(AN[-]?\d{6,})\b', 0.9, 'TRANSMITTER_ANALYZER'),
            
            # Regulatory/Registration numbers
            (r'\b([A-Z]{1,3}\d{5,})\b', 0.9, 'REGULATORY_NUMBER'),  # K011111, FDA12345
            (r'\bFDA[-\s]*(\d{6,})\b', 0.95, 'REGULATORY_NUMBER'),
            (r'\b(K\d{6})\b', 0.95, 'REGULATORY_NUMBER'),  # FDA clearance numbers
            
            # Manufacturing specifications (technical measurements)
            (r'\b(\d+\.?\d*\s*mm\s+.*?\s+\d+oz\s+package)\b', 0.85, 'MANUFACTURING_SPEC'),
            (r'\b(\d+\.?\d*\s*mm\s+type\s+thread)\b', 0.85, 'MANUFACTURING_SPEC'),
            (r'\b(\d+oz\s+package)\b', 0.8, 'MANUFACTURING_SPEC'),
            (r'\b(ISO\s+\d+)\b', 0.8, 'MANUFACTURING_SPEC'),  # ISO standards
            
            # Standalone alphanumeric codes
            (r'\b([A-Z]{2,}\d{4,})\b', 0.7, 'MANUFACTURING_NUMBER'),
            (r'\b(\d{4,}[A-Z]{2,})\b', 0.7, 'MANUFACTURING_NUMBER'),
            (r'\b([A-Z]\d+[A-Z]+\d*)\b', 0.75, 'MANUFACTURING_NUMBER'),  # A123B, X1Y2Z3
        ]
        
        for pattern, confidence, detection_type in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                detected_text = match.group(1) if match.groups() else match.group()
                
                # Check false positives
                if self._is_false_positive(detected_text):
                    continue
                
                findings.append({
                    'type': detection_type,
                    'original': detected_text,
                    'start': match.start(1) if match.groups() else match.start(),
                    'end': match.end(1) if match.groups() else match.end(),
                    'confidence': confidence,
                    'method': 'manufacturing_pattern'
                })
        
        return findings
    
    def detect_targeted_presidio(self, text: str, existing_findings: List[Dict]) -> List[Dict]:
        """Use Presidio selectively for missed company names and edge cases"""
        if not self.presidio_analyzer:
            return []
        
        findings = []
        
        # 1. Find capitalized words our regex missed
        capitalized_pattern = r'\b[A-Z][a-z]{2,}\b'
        for match in re.finditer(capitalized_pattern, text):
            word = match.group()
            start, end = match.start(), match.end()
            
            # Skip if already found by regex or is false positive
            if (self._is_false_positive(word) or 
                self._already_found_by_existing(start, end, existing_findings)):
                continue
            
            # Check if word is in manufacturing/company context
            context_start = max(0, start - 30)
            context_end = min(len(text), end + 30)
            context = text[context_start:context_end].lower()
            
            manufacturing_triggers = [
                'manufacturer', 'company', 'made by', 'produced by', 'distributor',
                'supplier', 'corporation', 'inc', 'ltd', 'llc', 'contacted'
            ]
            
            if any(trigger in context for trigger in manufacturing_triggers):
                # Run Presidio ORG detection on just this word
                try:
                    word_results = self.presidio_analyzer.analyze(
                        word, entities=['ORG'], language='en'
                    )
                    
                    if word_results and word_results[0].score > 0.6:
                        findings.append({
                            'type': 'ORGANIZATION',
                            'original': word,
                            'start': start,
                            'end': end,
                            'confidence': word_results[0].score * 0.8,  # Reduce confidence slightly
                            'method': 'presidio_targeted'
                        })
                        self._debug_print(f"Presidio caught company name: {word}")
                
                except Exception as e:
                    self._debug_print(f"Presidio error on word '{word}': {e}")
        
        # 2. Find remaining alphanumeric sequences our patterns missed
        alphanumeric_patterns = [
            r'\b[A-Z]{1,2}\d{4,}[A-Z]*\b',    # K011111, AB1234C
            r'\b\d{2,}[A-Z]{2,}\d*\b',        # 123ABC, 45XYZ789
        ]
        
        for pattern in alphanumeric_patterns:
            for match in re.finditer(pattern, text):
                code = match.group()
                start, end = match.start(), match.end()
                
                # Skip if already found or is false positive
                if (self._is_false_positive(code) or 
                    self._already_found_by_existing(start, end, existing_findings)):
                    continue
                
                # Check if in regulatory/technical context
                context_start = max(0, start - 20)
                context_end = min(len(text), end + 20)
                context = text[context_start:context_end].lower()
                
                regulatory_triggers = [
                    'registration', 'clearance', 'approval', 'fda', 'model',
                    'serial', 'part', 'regulatory', 'compliance'
                ]
                
                if any(trigger in context for trigger in regulatory_triggers):
                    findings.append({
                        'type': 'REGULATORY_NUMBER',
                        'original': code,
                        'start': start,
                        'end': end,
                        'confidence': 0.85,
                        'method': 'alphanumeric_pattern'
                    })
                    self._debug_print(f"Alphanumeric pattern caught: {code}")
        
        return findings
    
    def _already_found_by_existing(self, start: int, end: int, existing_findings: List[Dict]) -> bool:
        """Check if position range overlaps with existing findings"""
        for finding in existing_findings:
            if (finding['start'] <= start < finding['end'] or 
                finding['start'] < end <= finding['end'] or
                start <= finding['start'] < end):
                return True
        return False
    
    def remove_overlaps(self, findings: List[Dict]) -> List[Dict]:
        """Remove overlapping findings, keeping higher confidence ones"""
        if not findings:
            return findings
        
        # Sort by start position
        sorted_findings = sorted(findings, key=lambda x: x['start'])
        
        filtered = []
        for finding in sorted_findings:
            # Check if this finding overlaps with any existing ones
            overlaps = False
            for existing in filtered:
                if (finding['start'] < existing['end'] and finding['end'] > existing['start']):
                    # Overlap detected - keep the higher confidence one
                    if finding['confidence'] > existing['confidence']:
                        filtered.remove(existing)
                    else:
                        overlaps = True
                    break
            
            if not overlaps:
                filtered.append(finding)
        
        return filtered
    
    def classify_findings(self, findings: List[Dict]) -> List[Dict]:
        """Classify findings into B4/B6 categories"""
        classified = []
        
        # B6 (Patient/Medical Information)
        b6_types = ['NAME', 'PHONE', 'EMAIL', 'ADDRESS', 'LOCATION', 'ZIP', 'SSN', 'MEDICAL_ID', 'DATE', 'ID', 'FACILITY', 'PROFANITY']
        
        # B4 (Trade Secret/Commercial Information)
        b4_types = ['PHARMACEUTICAL', 'MANUFACTURING_NUMBER', 'TRANSMITTER_ANALYZER', 'FINANCIAL', 'COMMERCIAL', 
                   'REGULATORY_NUMBER', 'MANUFACTURING_SPEC', 'ORGANIZATION']
        
        for finding in findings:
            finding_copy = finding.copy()
            
            if finding['type'] in b6_types:
                finding_copy['classification'] = 'B6'
                finding_copy['category'] = 'Patient/Medical Information'
            elif finding['type'] in b4_types:
                finding_copy['classification'] = 'B4'
                finding_copy['category'] = 'Trade Secret/Commercial Information'
            else:
                # Default to B6 for safety
                finding_copy['classification'] = 'B6'
                finding_copy['category'] = 'Patient/Medical Information (default)'
            
            finding_copy['description'] = finding_copy['category']
            classified.append(finding_copy)
        
        return classified
    
    def run_detection(self, text: str) -> Tuple[str, List[Dict]]:
        """Run complete detection on text"""
        all_findings = []
        
        self._debug_print("=== SIMPLIFIED DETECTION ENGINE ===")
        
        # Run all detection methods
        all_findings.extend(self.detect_names(text))
        all_findings.extend(self.detect_locations(text))
        all_findings.extend(self.detect_contact_info(text))
        all_findings.extend(self.detect_dates(text))
        all_findings.extend(self.detect_medical_ids(text))
        all_findings.extend(self.detect_pharmaceuticals(text))
        all_findings.extend(self.detect_manufacturing_info(text))
        all_findings.extend(self.detect_profanity(text))
        all_findings.extend(self.detect_financial_info(text))
        all_findings.extend(self.detect_targeted_presidio(text, all_findings))
        
        self._debug_print(f"Total raw findings: {len(all_findings)}")
        
        # Remove overlaps
        unique_findings = self.remove_overlaps(all_findings)
        self._debug_print(f"After removing overlaps: {len(unique_findings)}")
        
        # Classify findings
        classified_findings = self.classify_findings(unique_findings)
        
        # Apply redactions
        redacted_text = text
        for finding in reversed(sorted(classified_findings, key=lambda x: x['start'])):
            start, end = finding['start'], finding['end']
            classification = finding['classification']
            replacement = f'[REDACTED_{classification}]'
            redacted_text = redacted_text[:start] + replacement + redacted_text[end:]
        
        # Summary
        b4_count = len([f for f in classified_findings if f['classification'] == 'B4'])
        b6_count = len([f for f in classified_findings if f['classification'] == 'B6'])
        self._debug_print(f"FINAL RESULTS: {len(classified_findings)} total, {b4_count} B4, {b6_count} B6")
        
        return redacted_text, classified_findings

# Global instance
simplified_engine = SimplifiedRedactionEngine()

# Compatibility functions for existing web app
def run_3500a_redaction(extracted_fields: Dict[str, str]) -> Tuple[Dict[str, str], List[Dict]]:
    all_findings = []
    redacted_fields = {}
    
    for field_id, content in extracted_fields.items():
        if not content.strip():
            redacted_fields[field_id] = content
            continue
        
        redacted_content, field_findings = simplified_engine.run_detection(content)
        for finding in field_findings:
            finding['field'] = field_id
            all_findings.append(finding)
        redacted_fields[field_id] = redacted_content
    
    return redacted_fields, all_findings

def detect_b4_content(text: str) -> List[Dict]:
    _, findings = simplified_engine.run_detection(text)
    return [f for f in findings if f['classification'] == 'B4']

def detect_b6_content(text: str) -> List[Dict]:
    _, findings = simplified_engine.run_detection(text)
    return [f for f in findings if f['classification'] == 'B6']

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 simplified_redaction.py input_file output_file")
        return 1
    
    try:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"Processing: {sys.argv[1]}")
        redacted_content, findings = simplified_engine.run_detection(content)
        
        with open(sys.argv[2], 'w', encoding='utf-8') as f:
            f.write(redacted_content)
        
        print(f"✅ Simplified redaction completed!")
        
        # Show results breakdown
        b4_count = len([f for f in findings if f['classification'] == 'B4'])
        b6_count = len([f for f in findings if f['classification'] == 'B6'])
        print(f"🏭 B4 (Trade Secret): {b4_count} items")
        print(f"🏥 B6 (Patient/Medical): {b6_count} items")
        
        return 0
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main())
