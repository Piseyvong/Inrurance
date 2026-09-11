# Chatbot UI Enhancement Plan

## Overview
Enhance the Insurance AI Agent chatbot UI to properly format claim status responses, policy information, and structured data displays.

## Current Issues
1. **Claim status responses** are plain text with no visual hierarchy
2. **Policy information** lacks structured presentation
3. **No markdown rendering** for formatted responses
4. **No status badges** for claim/policy states
5. **No interactive elements** for claim details

## Enhancement Strategy

### Phase 1: Message Rendering Engine
**File: `frontend/src/components/InsuranceAgentBubble.tsx`**

Add a custom markdown renderer for agent messages:
- Parse bold text (`**text**`)
- Parse headers (`## text`)
- Parse bullet points (`- item`)
- Parse numbered lists (`1. item`)
- Parse inline code and code blocks

### Phase 2: Structured Data Components
**File: `frontend/src/components/InsuranceAgentBubble.tsx`**

Create reusable components for:
1. **StatusBadge** - Color-coded claim/policy status indicators
2. **ClaimCard** - Structured claim information display
3. **PolicyCard** - Structured policy information display
4. **DocumentList** - Required documents checklist
5. **ActionButtons** - Interactive next-step buttons

### Phase 3: CSS Styling
**File: `frontend/src/styles.css`**

Add styles for:
- Status badges (approved, pending, rejected, human_review_required)
- Structured data cards
- Formatted message content
- Interactive elements

## Implementation Details

### 1. Message Type System
```typescript
type Message = {
  sender: "agent" | "user";
  text: string;
  actions?: AgentAction[];
  structuredData?: StructuredData;
};

type StructuredData = {
  type: "claim_status" | "policy_info" | "document_list";
  data: ClaimStatus | PolicyInfo | DocumentList;
};
```

### 2. Claim Status Component
```typescript
function ClaimStatusCard({ claim }: { claim: ClaimStatus }) {
  return (
    <div className="claimStatusCard">
      <div className="claimHeader">
        <span className="claimId">#{claim.id}</span>
        <StatusBadge status={claim.status} />
      </div>
      <div className="claimDetails">
        <div className="detailRow">
          <span className="label">Type</span>
          <span className="value">{claim.claim_type}</span>
        </div>
        <div className="detailRow">
          <span className="label">Amount</span>
          <span className="value">${claim.amount}</span>
        </div>
        {claim.documents && (
          <DocumentChecklist documents={claim.documents} />
        )}
      </div>
      {claim.nextSteps && (
        <div className="nextSteps">
          <strong>Next Steps:</strong>
          <ul>{claim.nextSteps.map(step => <li key={step}>{step}</li>)}</ul>
        </div>
      )}
    </div>
  );
}
```

### 3. Status Badge Component
```typescript
function StatusBadge({ status }: { status: string }) {
  const statusConfig = {
    approved: { color: "#15803d", bg: "#dcfce7", label: "Approved" },
    pending: { color: "#92400e", bg: "#fef3c7", label: "Pending" },
    rejected: { color: "#b91c1c", bg: "#fee2e2", label: "Rejected" },
    human_review_required: { color: "#1e40af", bg: "#dbeafe", label: "Under Review" },
    waiting_for_documents: { color: "#6b21a8", bg: "#f3e8ff", label: "Awaiting Docs" },
  };
  
  const config = statusConfig[status] || statusConfig.pending;
  
  return (
    <span className="statusBadge" style={{ background: config.bg, color: config.color }}>
      {config.label}
    </span>
  );
}
```

### 4. Policy Info Component
```typescript
function PolicyInfoCard({ policy }: { policy: PolicyInfo }) {
  return (
    <div className="policyInfoCard">
      <div className="policyHeader">
        <span className="policyNumber">{policy.policy_number}</span>
        <StatusBadge status={policy.status} />
      </div>
      <div className="policyDetails">
        <div className="detailRow">
          <span className="label">Product</span>
          <span className="value">{policy.product_name}</span>
        </div>
        <div className="detailRow">
          <span className="label">Coverage</span>
          <span className="value">{policy.coverage_type}</span>
        </div>
        <div className="detailRow">
          <span className="label">Valid Until</span>
          <span className="value">{policy.end_date}</span>
        </div>
      </div>
      {policy.benefits && (
        <div className="policyBenefits">
          <strong>Covered Benefits:</strong>
          <ul>{policy.benefits.map(benefit => <li key={benefit}>{benefit}</li>)}</ul>
        </div>
      )}
    </div>
  );
}
```

### 5. Document Checklist Component
```typescript
function DocumentChecklist({ documents }: { documents: Document[] }) {
  return (
    <div className="documentChecklist">
      <strong>Required Documents:</strong>
      <ul>
        {documents.map(doc => (
          <li key={doc.name} className={doc.submitted ? "submitted" : "pending"}>
            <span className="checkIcon">{doc.submitted ? "✓" : "○"}</span>
            <span>{doc.name}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

## CSS Additions

### Status Badge Styles
```css
.statusBadge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 4px 10px;
  letter-spacing: 0.02em;
}

.statusBadge.approved {
  background: #dcfce7;
  color: #15803d;
}

.statusBadge.pending {
  background: #fef3c7;
  color: #92400e;
}

.statusBadge.rejected {
  background: #fee2e2;
  color: #b91c1c;
}

.statusBadge.human_review_required {
  background: #dbeafe;
  color: #1e40af;
}
```

### Claim Card Styles
```css
.claimStatusCard {
  background: #fff;
  border: 1px solid #dce8e4;
  border-radius: 14px;
  padding: 16px;
  margin: 8px 0;
}

.claimHeader {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.claimId {
  font-weight: 700;
  color: #0d2724;
}

.claimDetails {
  display: grid;
  gap: 8px;
}

.detailRow {
  display: flex;
  justify-content: space-between;
  font-size: 0.85rem;
}

.detailRow .label {
  color: #6b817d;
}

.detailRow .value {
  font-weight: 600;
  color: #0d2724;
}
```

### Document Checklist Styles
```css
.documentChecklist {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #dce8e4;
}

.documentChecklist ul {
  list-style: none;
  padding: 0;
  margin: 8px 0 0;
}

.documentChecklist li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 0.85rem;
}

.documentChecklist li.submitted {
  color: #15803d;
}

.documentChecklist li.pending {
  color: #92400e;
}

.checkIcon {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-size: 0.75rem;
}

.documentChecklist li.submitted .checkIcon {
  background: #dcfce7;
  color: #15803d;
}

.documentChecklist li.pending .checkIcon {
  background: #fef3c7;
  color: #92400e;
}
```

### Next Steps Styles
```css
.nextSteps {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #dce8e4;
}

.nextSteps strong {
  font-size: 0.85rem;
  color: #0d2724;
}

.nextSteps ul {
  margin: 8px 0 0;
  padding-left: 20px;
}

.nextSteps li {
  font-size: 0.85rem;
  line-height: 1.6;
  color: #36514d;
}
```

## Backend Response Enhancement

### Chat Router Updates
**File: `app/routers/chat.py`**

Enhance the response to include structured data:

```python
@router.post("", response_model=GuideChatResponse)
async def chat_with_guide(payload: GuideChatRequest, ...):
    # ... existing code ...
    
    # Parse claim status queries
    if "claim status" in lower or "my claim" in lower:
        # Find the specific claim or list all
        claim_number = extract_claim_number(payload.message)
        if claim_number:
            claim = find_claim(claims, claim_number)
            if claim:
                context += f"\n\nCLAIM_STATUS_DATA: {json.dumps(claim.to_dict())}"
                context += f"\n\nDOCUMENT_CHECKLIST: {json.dumps(get_required_documents(claim))}"
    
    # Parse policy queries
    if "my policies" in lower or "what policies" in lower:
        context += f"\n\nPOLICIES_DATA: {json.dumps([p.to_dict() for p in policies])}"
    
    # ... rest of existing code ...
```

### Schema Updates
**File: `app/schemas/chat.py`**

Add structured data types:

```python
from pydantic import BaseModel
from typing import Optional, List

class ClaimStatusData(BaseModel):
    id: int
    claim_type: str
    status: str
    amount: Optional[float]
    documents: List[dict]
    next_steps: List[str]

class PolicyInfoData(BaseModel):
    policy_number: str
    product_name: str
    status: str
    coverage_type: str
    end_date: str
    benefits: List[str]

class GuideChatResponse(BaseModel):
    reply: str
    mode: str
    actions: List[dict]
    structured_data: Optional[dict] = None  # New field
```

## Files to Modify

### Frontend
1. `frontend/src/components/InsuranceAgentBubble.tsx`
   - Add message parsing logic
   - Add structured data components
   - Add status badge component
   - Add claim/policy card components

2. `frontend/src/styles.css`
   - Add all new CSS classes
   - Add responsive styles

### Backend
1. `app/routers/chat.py`
   - Add structured data extraction
   - Enhance context building

2. `app/schemas/chat.py`
   - Add new data models

## Testing Strategy

1. **Unit Tests**
   - Test message parsing functions
   - Test component rendering with mock data

2. **Integration Tests**
   - Test chat endpoint with structured responses
   - Test frontend-backend data flow

3. **Visual Testing**
   - Verify status badges render correctly
   - Verify claim/policy cards display properly
   - Test responsive behavior on mobile

## Implementation Order

1. ✅ Add CSS styles for new components
2. ✅ Create StatusBadge component
3. ✅ Create ClaimStatusCard component
4. ✅ Create PolicyInfoCard component
5. ✅ Create DocumentChecklist component
6. ✅ Add message parsing logic
7. ✅ Update chat router for structured data
8. ✅ Update chat schemas
9. ✅ Test all components
10. ✅ Add responsive styles

## Success Criteria

- [ ] Claim status displays with proper formatting and status badges
- [ ] Policy information shows in structured cards
- [ ] Document checklists show submitted/pending status
- [ ] Next steps are clearly displayed
- [ ] All components are responsive
- [ ] No breaking changes to existing functionality
