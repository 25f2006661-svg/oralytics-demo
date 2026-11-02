export type SampleType = 'photo';
export type DemoScenario = 'Balanced demo' | 'Lower review demo' | 'Higher review demo';

export interface ScreeningInput {
  sample_type: SampleType;
  panels: string[];
  scenario: DemoScenario;
  age?: number;
  participant_code: string;
  consent: boolean;
  collected_at: string;
}

export interface ScreeningIndicator {
  name: string;
  value: number;
  unit: string;
  explanation: string;
  is_simulated: true;
}

export interface ScreeningAssessment {
  category: string;
  signal_score: number;
  explanation: string[];
  missing_inputs: string[];
  rule_version: string;
  is_simulated: true;
  disclaimer: string;
}

export interface ScreeningAnalysis {
  record: { id: number; record_code: string; status: string; is_simulated: true; data_source: string; collected_at: string };
  sample_type: SampleType;
  scenario: DemoScenario;
  selected_panels: string[];
  readings: ScreeningIndicator[];
  assessment: ScreeningAssessment;
  timestamp: string;
  is_simulated: true;
  participant_code?: string;
}

export interface ScreeningRecord {
  id: string;
  backendId?: number;
  date: string;
  sample: string;
  panels: string[];
  priority: string;
  status: string;
  referral: string;
  report?: ScreeningAnalysis;
  participantCode?: string;
}
