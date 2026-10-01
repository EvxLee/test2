// Mock response simulating what the /document-search endpoint will return.
// Shape must stay in sync with the shared contract:
//   document_id, chunk_text, page, section_title, metadata

export interface SearchResultChunk {
  document_id: string;
  chunk_text: string;
  page: number;
  section_title: string;
  metadata: Record<string, unknown>;
}

export interface SearchResponse {
  results: SearchResultChunk[];
}

export const mockSearchResponse: SearchResponse = {
  results: [
    {
      document_id: "doc_001",
      chunk_text:
        "This contract outlines the partnership terms between GCED and the startup. Both parties agree to a 12-month pilot engagement beginning Q1 2026.",
      page: 2,
      section_title: "Agreement Overview",
      metadata: {
        file_name: "GCED_Partnership_Agreement_2026.pdf",
        category: "Contracts",
        owner: "Alex Doe",
      },
    },
    {
      document_id: "doc_002",
      chunk_text:
        "The financial projections indicate a 3x return on investment within 18 months, based on current market penetration rates in the Southeast Asia region.",
      page: 5,
      section_title: "Financial Projections",
      metadata: {
        file_name: "Startup_Pitch_Deck_EcoFlux.pptx",
        category: "Pitch Decks",
        owner: "Alex Doe",
      },
    },
    {
      document_id: "doc_003",
      chunk_text:
        "Technical architecture relies on a microservices approach with containerized deployments. Latency targets are under 200ms for 99th percentile.",
      page: 8,
      section_title: "Technical Architecture",
      metadata: {
        file_name: "AsterAI_Technical_Spec.docx",
        category: "Technical Docs",
        owner: "Alex Doe",
      },
    },
    {
      document_id: "doc_004",
      chunk_text:
        "Market analysis shows strong demand in the cleantech vertical. Competitive landscape includes three major incumbents with limited AI-native offerings.",
      page: 3,
      section_title: "Market Analysis",
      metadata: {
        file_name: "Cleantech_Market_Report_2025.pdf",
        category: "Reports",
        owner: "Alex Doe",
      },
    },
    {
      document_id: "doc_005",
      chunk_text:
        "The evaluation scorecard for Track A startups uses five criteria: innovation, scalability, team strength, market fit, and GCED alignment.",
      page: 1,
      section_title: "Evaluation Criteria",
      metadata: {
        file_name: "GCED_Evaluation_Rubric.pdf",
        category: "Evaluation",
        owner: "Alex Doe",
      },
    },
  ],
};
