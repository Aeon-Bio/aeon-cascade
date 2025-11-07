<script lang="ts">
	import Card from '$lib/components/ui/Card.svelte';
</script>

<svelte:head>
	<title>Terms of Service - Aeon Cascade</title>
</svelte:head>

<div class="min-h-screen bg-gray-50">
	<header class="bg-white border-b border-gray-200">
		<div class="container mx-auto px-4 py-6">
			<div class="flex items-center justify-between">
				<div>
					<h1 class="text-3xl font-bold text-gray-900">Terms of Service</h1>
					<p class="text-sm text-gray-600 mt-1">Aeon Cascade - Mechanism Explorer</p>
				</div>
				<a href="/" class="text-primary-600 hover:text-primary-700 text-sm font-medium">
					← Back to Home
				</a>
			</div>
		</div>
	</header>

	<main class="container mx-auto px-4 py-8 max-w-4xl">
		<Card padding="lg">
			<div class="prose prose-sm max-w-none">
				<p class="text-xs text-gray-500 mb-6">Last Updated: November 2, 2025</p>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">1. Service Description</h2>
					<p class="text-gray-700 mb-3">
						Aeon Cascade is a <strong>mechanism explorer</strong> that displays validated biological pathways
						from peer-reviewed scientific literature via the INDRA bio-ontology database.
					</p>
					<div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-3">
						<p class="text-sm text-blue-900 font-medium">What This System IS:</p>
						<ul class="list-disc list-inside text-sm text-blue-800 mt-2 space-y-1">
							<li>An information display tool showing biological mechanisms from scientific papers</li>
							<li>A research aid for exploring causal pathways with evidence transparency</li>
							<li>Educational content for understanding systems biology</li>
						</ul>
					</div>
					<div class="bg-red-50 border border-red-200 rounded-lg p-4">
						<p class="text-sm text-red-900 font-medium">What This System is NOT:</p>
						<ul class="list-disc list-inside text-sm text-red-800 mt-2 space-y-1">
							<li>Medical advice or clinical decision support</li>
							<li>A diagnostic tool or disease prediction system</li>
							<li>Personalized health recommendations</li>
							<li>A substitute for professional medical consultation</li>
						</ul>
					</div>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">2. Regulatory Positioning (21st Century Cures Act)</h2>
					<p class="text-gray-700 mb-3">
						This system qualifies for the <strong>Clinical Decision Support (CDS) software exemption</strong>
						under Section 3060 of the 21st Century Cures Act (21 U.S.C. 360j(o)(1)(E)) because it:
					</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>
							<strong>Displays information</strong> from peer-reviewed literature (INDRA bio-ontology, 47,000+ pathways)
						</li>
						<li>
							<strong>Provides transparent evidence</strong> (paper counts, belief scores, temporal dynamics)
						</li>
						<li>
							<strong>Does NOT interpret or analyze</strong> individual patient data
						</li>
						<li>
							<strong>Requires independent review</strong> by healthcare providers before clinical use
						</li>
					</ul>
					<p class="text-gray-700 mt-3">
						As such, Aeon Cascade is <strong>not a medical device</strong> and is exempt from FDA regulation
						under this provision.
					</p>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">3. No Medical Advice</h2>
					<div class="bg-yellow-50 border-l-4 border-yellow-400 p-4">
						<p class="text-yellow-900 font-semibold mb-2">⚠️ CRITICAL DISCLAIMER</p>
						<p class="text-sm text-yellow-800">
							All information provided by Aeon Cascade represents <strong>population-level biological mechanisms</strong>
							derived from scientific literature. This is NOT personalized medical advice.
						</p>
					</div>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4 mt-4">
						<li>Results show <strong>typical effects</strong> observed in research populations</li>
						<li>YOUR individual response may vary due to genetics, microbiome, environment, and health status</li>
						<li>Effect sizes and temporal dynamics are <strong>statistical averages</strong>, not guarantees</li>
						<li>
							<strong>Always consult a qualified healthcare provider</strong> before making health decisions
						</li>
					</ul>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">4. Data Sources and Accuracy</h2>
					<p class="text-gray-700 mb-3">
						Causal pathways are sourced from:
					</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>
							<strong>INDRA bio-ontology</strong>: 47,000+ causal relationships from peer-reviewed papers
						</li>
						<li>
							<strong>Scientific databases</strong>: PubMed, pathway databases (Reactome, PathwayCommons)
						</li>
						<li>
							<strong>Environmental data</strong>: IQAir pollution API (when available)
						</li>
					</ul>
					<p class="text-gray-700 mt-3">
						<strong>Accuracy limitations:</strong>
					</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>Scientific knowledge evolves; pathways reflect current literature at time of query</li>
						<li>Belief scores and effect sizes are computational estimates, not clinical measurements</li>
						<li>Path length limited to 3 hops (inherent INDRA API constraint)</li>
						<li>System cannot model feedback loops or complex multi-organ dynamics</li>
					</ul>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">5. User Responsibilities</h2>
					<p class="text-gray-700 mb-3">By using Aeon Cascade, you agree to:</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>
							<strong>Understand limitations</strong>: This system shows population biology, not personalized predictions
						</li>
						<li>
							<strong>Consult healthcare providers</strong>: Share mechanisms with your doctor, discuss monitoring plans
						</li>
						<li>
							<strong>Validate with biomarker testing</strong>: Monitor YOUR response at suggested timepoints
						</li>
						<li>
							<strong>Do not self-diagnose</strong>: Displayed pathways are NOT diagnostic conclusions
						</li>
						<li>
							<strong>Report inaccuracies</strong>: If you find biological errors, contact us for review
						</li>
					</ul>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">6. Prohibited Uses</h2>
					<p class="text-gray-700 mb-3">You may NOT use Aeon Cascade to:</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>Replace professional medical diagnosis or treatment</li>
						<li>Make clinical decisions without healthcare provider consultation</li>
						<li>Claim that displayed mechanisms guarantee outcomes in individuals</li>
						<li>Misrepresent the system as FDA-approved medical device</li>
						<li>Scrape or redistribute INDRA data without proper attribution</li>
					</ul>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">7. Limitation of Liability</h2>
					<div class="bg-gray-50 border border-gray-300 rounded-lg p-4">
						<p class="text-sm text-gray-800">
							<strong>TO THE MAXIMUM EXTENT PERMITTED BY LAW</strong>, Aeon Cascade and its creators
							provide this service <strong>"AS IS"</strong> with no warranties, express or implied.
						</p>
						<p class="text-sm text-gray-800 mt-2">
							We are NOT liable for:
						</p>
						<ul class="list-disc list-inside text-sm text-gray-700 mt-2 space-y-1 ml-4">
							<li>Health outcomes resulting from use of displayed information</li>
							<li>Decisions made based on system output without professional medical consultation</li>
							<li>Inaccuracies in third-party data sources (INDRA, scientific papers)</li>
							<li>Technical errors, downtime, or data loss</li>
						</ul>
					</div>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">8. Evidence Transparency</h2>
					<p class="text-gray-700 mb-3">
						All displayed pathways include:
					</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>
							<strong>Paper counts</strong>: Number of peer-reviewed studies supporting the relationship
						</li>
						<li>
							<strong>Belief scores</strong>: INDRA's confidence in the causal relationship (0-1 scale)
						</li>
						<li>
							<strong>Effect sizes</strong>: Population-average magnitude (NOT individual predictions)
						</li>
						<li>
							<strong>Temporal dynamics</strong>: Typical lag times based on mechanism type
						</li>
					</ul>
					<p class="text-gray-700 mt-3">
						Color coding indicates strength:
					</p>
					<ul class="list-disc list-inside text-gray-700 space-y-1 ml-4">
						<li><span class="text-green-600 font-semibold">Green</span>: Very high evidence (100+ papers, belief &gt;0.7)</li>
						<li><span class="text-blue-600 font-semibold">Blue</span>: High evidence (10-100 papers, belief 0.5-0.7)</li>
						<li><span class="text-yellow-600 font-semibold">Yellow</span>: Low evidence (&lt;10 papers, belief &lt;0.5) - validate with additional research</li>
					</ul>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">9. Privacy and Data Collection</h2>
					<p class="text-gray-700 mb-3">
						See our <a href="/privacy" class="text-primary-600 hover:text-primary-700 font-medium">Privacy Policy</a>
						for details on data collection and usage.
					</p>
					<p class="text-gray-700">
						<strong>Summary:</strong> We collect minimal data (queries, session info) and do NOT share
						personal health information with third parties.
					</p>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">10. Changes to Terms</h2>
					<p class="text-gray-700">
						We may update these Terms of Service as the system evolves. Changes will be posted on this page
						with an updated "Last Updated" date. Continued use after changes constitutes acceptance of new terms.
					</p>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">11. Contact Information</h2>
					<p class="text-gray-700">
						For questions about these Terms of Service, biological accuracy concerns, or system issues:
					</p>
					<ul class="list-none text-gray-700 space-y-2 mt-3">
						<li>
							<strong>Email:</strong> <a href="mailto:support@aeoncascade.com" class="text-primary-600 hover:text-primary-700">support@aeoncascade.com</a>
						</li>
						<li>
							<strong>Documentation:</strong> <a href="/about" class="text-primary-600 hover:text-primary-700">About Aeon Cascade</a>
						</li>
					</ul>
				</section>

				<div class="border-t border-gray-300 pt-6 mt-8">
					<p class="text-sm text-gray-600">
						By using Aeon Cascade, you acknowledge that you have read, understood, and agree to be bound by these Terms of Service.
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
