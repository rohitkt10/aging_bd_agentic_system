# Rethinking phase 2 critic refinement

The overall goal here is to establish a collaborative feedback loop modeled upon the standard scientific manuscript subsmission/review/rebuttal cycle. 

## What do we want the critic to do?

The critic agent should take in data from the research agent (gene_evidence dict, state of knowledge, final gene list with scores, final iteration summary and whatever else might be useful) and produce 1. commentary on the quality of information (i.e. ultimately curated scored gene list but also general knowledge in the form of the text summary or gene evidence dict or whatever) curated so far. 2. provide recommendations on refinement. this could entail more requests to do research gaps or verify some detail (maybe research agent scored a particular gene too highly and it feels suspicious)…whatever. essentially acting the way a manuscript reviewer might act - provide a high level review, comment on strengths and weakness of current state of knowledge, actionable research recommendations and a pass/fail grade. 

## What do we want the refinement agent to do?

The refinement should essentially function in the way that a researcher reacts to a manuscript review. read through the review critically  and make an assessment on what makes sense and what doesnt, check the actionable recommendations of the critic and perform those things or more stuff or less stuff by making a judgement on their utility, and then do the new research needed, synthesize all that information, draft a response to the critic along and pass it back with an updated gene_evidence or scored gene list table or whatever else and wait for the reviewer to get back to it again. 

## How many iterations of this should we do?

Default to 2. cycle terminates early if critic gives a passing grade and also terminates at max iterations regardless of grade. 

## Notes

The critic should not concern itself with the iteration context. Its only job is to make a quality assessment on knowledge drafted by the researcher. The refinement agent on the other hand *should* concern itself with the iteration context. if we are only allowed 1 iteration for critic/refine then in the final (and only) refinement step, the agent must produce a finalized list ,making the best faith effort to incorporate reviewer suggestions but never blindly accepting reviewer’s words (just like human researcher does not blindly accept reviewer’s words) and still staying within the bounds of the actual research goal (if the goal is to produce 30-50 genes per process then we ultimately need that as the final output). The refinement agent must always have an eye on the actual final goal. The critic is detached from this process. Its only job is to review  (again, roughly mirroring a scientific manuscript review cycle).