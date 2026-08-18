# Example: rewrite a draft

## Input

```
In today's rapidly evolving business landscape, our Q3 initiative is not
just a process update. It is a testament to our unwavering commitment to
excellence. After extensive stakeholder consultation, we have aligned on
a path forward that leverages cutting-edge automation, ensuring seamless
outcomes across the board. Experts agree that organizations embracing
this transformation will be well-positioned for the road ahead.
```

## Audit (abridged)

```
draft.md:1: [scene-setting] "In today's rapidly evolving business landscape"
draft.md:1: [inflated-contrast] "is not just"
draft.md:2: [significance-inflation] "testament"
draft.md:3: [process-not-reason] "After extensive stakeholder consultation"
draft.md:4: [tacked-on-benefit] ", ensuring"
draft.md:5: [fake-authority] "Experts agree"
draft.md:5: [canned-conclusion] "the road ahead"
FAIL
```

## Output

```
Q3 changes how invoices get approved. Finance asked for the change
because manual approval added four days to every vendor payment. The
new flow auto-approves invoices under $5,000 with a matching PO; the
rest route to one approver instead of three. If it holds up in
October's close, we extend it to expense reports.
```

Every claim in the rewrite is checkable. Nothing was kept from the
original except its actual content, which turned out to be one sentence.
