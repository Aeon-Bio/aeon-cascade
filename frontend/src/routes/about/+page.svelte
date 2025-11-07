<script lang="ts">
	import Card from '$lib/components/ui/Card.svelte';
</script>

<svelte:head>
	<title>About - Aeon Cascade</title>
</svelte:head>

<div class="min-h-screen bg-gray-50">
	<header class="bg-white border-b border-gray-200">
		<div class="container mx-auto px-4 py-6">
			<div class="flex items-center justify-between">
				<div>
					<h1 class="text-3xl font-bold text-gray-900">About Aeon Cascade</h1>
					<p class="text-sm text-gray-600 mt-1">Mechanism Explorer for Informed Health Decisions</p>
				</div>
				<a href="/" class="text-primary-600 hover:text-primary-700 text-sm font-medium">
					← Back to Home
				</a>
			</div>
		</div>
	</header>

	<main class="container mx-auto px-4 py-8 max-w-4xl">
		<!-- Mission Statement -->
		<Card padding="lg">
			<div class="prose prose-sm max-w-none mb-8">
				<div class="bg-gradient-to-r from-primary-50 to-blue-50 border border-primary-200 rounded-lg p-6 mb-8">
					<h2 class="text-2xl font-bold text-gray-900 mb-3">Our Mission</h2>
					<p class="text-lg text-gray-800">
						Aeon Cascade empowers individuals and clinicians to <strong>explore validated biological mechanisms</strong>
						underlying health interventions, bridging the gap between population-level science and personalized health monitoring.
					</p>
				</div>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">What We Do</h2>
					<p class="text-gray-700 mb-4">
						Aeon Cascade is a <strong>mechanism explorer</strong> that translates peer-reviewed scientific literature
						into understandable causal pathways. We display:
					</p>
					<div class="grid md:grid-cols-2 gap-4">
						<div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
							<h3 class="font-semibold text-blue-900 mb-2 flex items-center">
								<svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
								</svg>
								Biological Mechanisms
							</h3>
							<p class="text-sm text-blue-800">
								How interventions (diet, pollution, medications) affect biomarkers through molecular pathways
							</p>
						</div>
						<div class="bg-green-50 border border-green-200 rounded-lg p-4">
							<h3 class="font-semibold text-green-900 mb-2 flex items-center">
								<svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
								</svg>
								Evidence Transparency
							</h3>
							<p class="text-sm text-green-800">
								Paper counts (3-312), belief scores (0.3-0.98), effect sizes - see the strength of every claim
							</p>
						</div>
						<div class="bg-purple-50 border border-purple-200 rounded-lg p-4">
							<h3 class="font-semibold text-purple-900 mb-2 flex items-center">
								<svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path>
								</svg>
								Temporal Dynamics
							</h3>
							<p class="text-sm text-purple-800">
								When effects occur (e.g., "Measure CRP at T+24h post-intervention to see effect")
							</p>
						</div>
						<div class="bg-orange-50 border border-orange-200 rounded-lg p-4">
							<h3 class="font-semibold text-orange-900 mb-2 flex items-center">
								<svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
									<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01"></path>
								</svg>
								Genetic Context
							</h3>
							<p class="text-sm text-orange-800">
								How genetic variants (e.g., GSTM1 null) modify pathway responses (optional user input)
							</p>
						</div>
					</div>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">How It Works</h2>
					<div class="space-y-4">
						<div class="flex items-start">
							<div class="flex-shrink-0 w-8 h-8 bg-primary-600 text-white rounded-full flex items-center justify-center font-bold mr-4">
								1
							</div>
							<div class="flex-1">
								<h3 class="font-semibold text-gray-900 mb-1">You Ask a Health Question</h3>
								<p class="text-sm text-gray-700">
									e.g., "How does PM2.5 air pollution affect inflammation biomarkers like CRP?"
								</p>
							</div>
						</div>
						<div class="flex items-start">
							<div class="flex-shrink-0 w-8 h-8 bg-primary-600 text-white rounded-full flex items-center justify-center font-bold mr-4">
								2
							</div>
							<div class="flex-1">
								<h3 class="font-semibold text-gray-900 mb-1">We Query the INDRA Bio-Ontology</h3>
								<p class="text-sm text-gray-700">
									INDRA (Harvard Medical School) has extracted 47,000+ causal relationships from peer-reviewed papers.
									We search for pathways connecting your query entities (PM2.5 → CRP).
								</p>
							</div>
						</div>
						<div class="flex items-start">
							<div class="flex-shrink-0 w-8 h-8 bg-primary-600 text-white rounded-full flex items-center justify-center font-bold mr-4">
								3
							</div>
							<div class="flex-1">
								<h3 class="font-semibold text-gray-900 mb-1">We Build a Causal Graph</h3>
								<p class="text-sm text-gray-700">
									Pathways are ranked by evidence (paper counts), confidence (belief scores), and path length.
									Result: PM2.5 → NF-κB → IL-6 → CRP (47 + 89 + 312 papers).
								</p>
							</div>
						</div>
						<div class="flex items-start">
							<div class="flex-shrink-0 w-8 h-8 bg-primary-600 text-white rounded-full flex items-center justify-center font-bold mr-4">
								4
							</div>
							<div class="flex-1">
								<h3 class="font-semibold text-gray-900 mb-1">You See Transparent Results</h3>
								<p class="text-sm text-gray-700">
									Interactive graph with evidence indicators, temporal guidance ("Measure CRP at T+24h"),
									and clear disclaimers (population biology ≠ personalized prediction).
								</p>
							</div>
						</div>
					</div>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">Why This Matters</h2>
					<div class="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-4">
						<p class="text-yellow-900 font-semibold mb-2">The Problem: Health Information Opacity</p>
						<ul class="list-disc list-inside text-sm text-yellow-800 space-y-1">
							<li>Clinical guidelines say "reduce inflammation" but don't explain <strong>HOW</strong> interventions work</li>
							<li>Patients told to "check biomarkers" but not <strong>WHEN</strong> to measure or <strong>WHAT</strong> to expect</li>
							<li>Individual variation ignored - population studies misapplied to personal health decisions</li>
						</ul>
					</div>
					<div class="bg-green-50 border-l-4 border-green-400 p-4">
						<p class="text-green-900 font-semibold mb-2">Our Solution: Mechanism Transparency + Monitoring Guidance</p>
						<ul class="list-disc list-inside text-sm text-green-800 space-y-1">
							<li>
								<strong>Understand WHY:</strong> See molecular mechanisms (PM2.5 → oxidative stress → NF-κB → IL-6)
							</li>
							<li>
								<strong>Know WHEN:</strong> Test biomarkers at suggested timepoints (T+6h, T+24h) based on cascade dynamics
							</li>
							<li>
								<strong>Validate YOUR response:</strong> Population biology shows what's possible; YOUR data shows what's actual
							</li>
						</ul>
					</div>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">Technology Stack</h2>
					<div class="grid md:grid-cols-3 gap-4">
						<div class="border border-gray-300 rounded-lg p-4">
							<h3 class="font-semibold text-gray-900 mb-2">Data Source</h3>
							<p class="text-sm text-gray-700">
								<strong>INDRA Bio-Ontology</strong> (Harvard Medical School): 47,000+ causal relationships
								from PubMed, pathway databases (Reactome, PathwayCommons), text mining
							</p>
						</div>
						<div class="border border-gray-300 rounded-lg p-4">
							<h3 class="font-semibold text-gray-900 mb-2">AI Reasoning</h3>
							<p class="text-sm text-gray-700">
								<strong>LangGraph Multi-Agent System</strong>: Supervisor orchestrates INDRA queries,
								web research (pollution data), result synthesis via AWS Bedrock (Claude Sonnet 4.5)
							</p>
						</div>
						<div class="border border-gray-300 rounded-lg p-4">
							<h3 class="font-semibold text-gray-900 mb-2">Frontend</h3>
							<p class="text-sm text-gray-700">
								<strong>SvelteKit</strong> with interactive graph visualization (Cytoscape.js),
								temporal timelines, evidence badges, comprehensive disclaimers
							</p>
						</div>
					</div>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">Ship Blockers: Quality Assurance</h2>
					<p class="text-gray-700 mb-4">
						Before public release, we systematically addressed 5 critical "Ship Blockers" to ensure biological accuracy and transparency:
					</p>
					<div class="space-y-3">
						<div class="flex items-start">
							<span class="text-green-600 font-bold mr-3">✅ #1</span>
							<div>
								<strong class="text-gray-900">Biological Correctness:</strong>
								<span class="text-gray-700">Validated pathways route through known mediators (IL-1β → IL-6 via NF-κB)</span>
							</div>
						</div>
						<div class="flex items-start">
							<span class="text-green-600 font-bold mr-3">✅ #2</span>
							<div>
								<strong class="text-gray-900">Transparent Failure Modes:</strong>
								<span class="text-gray-700">System warns "pathway not found" vs. "weak evidence" - no silent failures</span>
							</div>
						</div>
						<div class="flex items-start">
							<span class="text-green-600 font-bold mr-3">✅ #3</span>
							<div>
								<strong class="text-gray-900">Interface Contract Compliance:</strong>
								<span class="text-gray-700">Effect sizes ∈ [0,1], temporal lags ≥0, all edges validated</span>
							</div>
						</div>
						<div class="flex items-start">
							<span class="text-green-600 font-bold mr-3">✅ #4</span>
							<div>
								<strong class="text-gray-900">Mechanism Description Library (MDL):</strong>
								<span class="text-gray-700">Standardized annotations for all 47,000 pathways (temporal lag, mechanism type, evidence)</span>
							</div>
						</div>
						<div class="flex items-start">
							<span class="text-green-600 font-bold mr-3">✅ #5</span>
							<div>
								<strong class="text-gray-900">Clinical Positioning:</strong>
								<span class="text-gray-700">"Mechanism Explorer for Informed Health Decisions" - not medical advice, not diagnostic tool</span>
							</div>
						</div>
					</div>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">Known Limitations (Transparency)</h2>
					<p class="text-gray-700 mb-3">
						We openly acknowledge constraints to set accurate expectations:
					</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>
							<strong>Path length ≤3 hops:</strong> INDRA API constraint limits complex multi-organ disease modeling
						</li>
						<li>
							<strong>DAG-only (no feedback loops):</strong> Cannot model reciprocal signaling or homeostatic regulation
						</li>
						<li>
							<strong>Population averages:</strong> Effect sizes reflect statistical means, not individual predictions
						</li>
						<li>
							<strong>Literature lag:</strong> Pathways reflect published science (not cutting-edge unpublished research)
						</li>
					</ul>
					<p class="text-gray-700 mt-3">
						See our <a href="https://github.com/yourusername/aeoncascade" class="text-primary-600 hover:text-primary-700" target="_blank" rel="noopener noreferrer">
						documentation on GitHub</a> for full technical details.
					</p>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">Use Cases</h2>
					<div class="grid md:grid-cols-2 gap-4">
						<div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
							<h3 class="font-semibold text-blue-900 mb-2">For Individuals</h3>
							<ul class="list-disc list-inside text-sm text-blue-800 space-y-1">
								<li>Understand <strong>why</strong> your doctor recommended an intervention</li>
								<li>Learn <strong>when</strong> to test biomarkers post-intervention</li>
								<li>See <strong>evidence strength</strong> (3 papers vs. 200 papers)</li>
								<li>Bring mechanism insights to healthcare consultations</li>
							</ul>
						</div>
						<div class="bg-green-50 border border-green-200 rounded-lg p-4">
							<h3 class="font-semibold text-green-900 mb-2">For Clinicians</h3>
							<ul class="list-disc list-inside text-sm text-green-800 space-y-1">
								<li>Explain mechanisms to patients in consultations</li>
								<li>Design personalized biomarker monitoring plans</li>
								<li>Explore genetic modifiers (GSTM1 variants, CYP450 polymorphisms)</li>
								<li>Validate intervention rationale with literature evidence</li>
							</ul>
						</div>
						<div class="bg-purple-50 border border-purple-200 rounded-lg p-4">
							<h3 class="font-semibold text-purple-900 mb-2">For Researchers</h3>
							<ul class="list-disc list-inside text-sm text-purple-800 space-y-1">
								<li>Generate hypotheses for studies (pathway exploration)</li>
								<li>Identify knowledge gaps (low-evidence pathways)</li>
								<li>Design intervention studies with temporal sampling</li>
								<li>Compare pathway representations across databases</li>
							</ul>
						</div>
						<div class="bg-orange-50 border border-orange-200 rounded-lg p-4">
							<h3 class="font-semibold text-orange-900 mb-2">For Educators</h3>
							<ul class="list-disc list-inside text-sm text-orange-800 space-y-1">
								<li>Teach systems biology with real-world examples</li>
								<li>Demonstrate evidence-based medicine principles</li>
								<li>Visualize causal reasoning in health science</li>
								<li>Show limitations of population studies for individuals</li>
							</ul>
						</div>
					</div>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">Regulatory Status</h2>
					<div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
						<p class="text-sm text-blue-900 font-semibold mb-2">
							Clinical Decision Support (CDS) Software Exemption
						</p>
						<p class="text-sm text-blue-800">
							Aeon Cascade qualifies for the <strong>21st Century Cures Act CDS exemption</strong>
							(21 U.S.C. 360j(o)(1)(E)) because it:
						</p>
						<ul class="list-disc list-inside text-sm text-blue-800 mt-2 space-y-1 ml-4">
							<li>Displays information from peer-reviewed literature (not device-generated analysis)</li>
							<li>Provides transparent evidence (paper counts, belief scores)</li>
							<li>Does NOT interpret or analyze individual patient data</li>
							<li>Requires independent review by healthcare providers before clinical use</li>
						</ul>
						<p class="text-sm text-blue-800 mt-3">
							<strong>Result:</strong> Not a medical device, exempt from FDA regulation under this provision.
						</p>
					</div>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">Open Science Commitment</h2>
					<p class="text-gray-700 mb-3">
						We believe in transparent, reproducible health information:
					</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>
							<strong>Open source code:</strong> Full system code on GitHub (MIT license)
						</li>
						<li>
							<strong>Public data sources:</strong> INDRA bio-ontology is publicly accessible
						</li>
						<li>
							<strong>Documented methods:</strong> See ARCHITECTURE_FIX_PLAN.md, SHIP_BLOCKERS_PROGRESS.md
						</li>
						<li>
							<strong>No paywalls:</strong> Free access to all mechanism exploration features
						</li>
					</ul>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">Contact Us</h2>
					<p class="text-gray-700 mb-3">
						We welcome feedback, bug reports, and collaboration inquiries:
					</p>
					<ul class="list-none text-gray-700 space-y-2">
						<li>
							<strong>Email:</strong> <a href="mailto:info@aeoncascade.com" class="text-primary-600 hover:text-primary-700">info@aeoncascade.com</a>
						</li>
						<li>
							<strong>GitHub:</strong> <a href="https://github.com/yourusername/aeoncascade" class="text-primary-600 hover:text-primary-700" target="_blank" rel="noopener noreferrer">github.com/yourusername/aeoncascade</a>
						</li>
						<li>
							<strong>Support:</strong> <a href="mailto:support@aeoncascade.com" class="text-primary-600 hover:text-primary-700">support@aeoncascade.com</a>
						</li>
						<li>
							<strong>Privacy:</strong> <a href="mailto:privacy@aeoncascade.com" class="text-primary-600 hover:text-primary-700">privacy@aeoncascade.com</a>
						</li>
					</ul>
				</section>

				<div class="border-t border-gray-300 pt-6 mt-8">
					<p class="text-sm text-gray-600">
						<strong>Disclaimer:</strong> Aeon Cascade is an information display tool, not a medical device.
						All displayed mechanisms represent population-level biology from peer-reviewed literature.
						Always consult qualified healthcare providers before making health decisions.
					</p>
				</div>
			</div>
		</Card>
	</main>

	<footer class="bg-white border-t border-gray-200 mt-12">
		<div class="container mx-auto px-4 py-6">
			<div class="flex items-center justify-between text-sm text-gray-600">
				<p>© 2025 Aeon Cascade. All rights reserved.</p>
				<div class="flex space-x-4">
					<a href="/terms" class="hover:text-primary-600">Terms of Service</a>
					<a href="/privacy" class="hover:text-primary-600">Privacy Policy</a>
					<a href="/about" class="hover:text-primary-600">About</a>
				</div>
			</div>
		</div>
	</footer>
</div>
