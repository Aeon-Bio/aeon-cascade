<script lang="ts">
	import PersonaSelector from '$lib/components/PersonaSelector.svelte';
	import GeneticBiomarkers from '$lib/components/GeneticBiomarkers.svelte';
	import BiomarkerTimeline from '$lib/components/BiomarkerTimeline.svelte';
	import QueryBuilder from '$lib/components/QueryBuilder.svelte';
	import CausalGraph from '$lib/components/CausalGraph.svelte';
	import InterventionPlanner from '$lib/components/InterventionPlanner.svelte';
	import CausalInsights from '$lib/components/CausalInsights.svelte';
	import FileUploader from '$lib/components/FileUploader.svelte';
	import GraphAnalysis from '$lib/components/GraphAnalysis.svelte';
	import TemporalCascade from '$lib/components/TemporalCascade.svelte';
	import ProgressStream from '$lib/components/ProgressStream.svelte';
	import { selectedPersona } from '$lib/stores/persona';
	import { causalGraph, keyInsights } from '$lib/stores/graph';
	import { isLoading, error } from '$lib/stores/query';
	import { queryINDRA, performIntervention } from '$lib/api/indra';
	import type { CausalDiscoveryRequest, InterventionResponse } from '$lib/types/models';

	let selectedTab = $state<'query' | 'graph' | 'interventions' | 'insights' | 'upload'>('query');
	let currentGraphId = $state<string | null>(null);
	let currentRequestId = $state<string | null>(null);
	let interventionResult = $state<InterventionResponse | null>(null);
	let showProgressStream = $state<boolean>(false);
	let causalInsightsData = $state<any>(null);

	async function handleQuerySubmit(event: CustomEvent<string>) {
		const queryText = event.detail;

		if (!$selectedPersona) return;

		// Build request
		const requestId = crypto.randomUUID();
		const request: CausalDiscoveryRequest = {
			request_id: requestId,
			query: {
				text: queryText,
				focus_biomarkers: $selectedPersona.keyBiomarkers
			},
			user_context: {
				user_id: $selectedPersona.id,
				current_biomarkers: Object.fromEntries(
					Object.entries($selectedPersona.biomarkers).map(([name, data]) => [name, data.value])
				),
				genetics: $selectedPersona.genetics,
				location_history: $selectedPersona.locationHistory.map(loc => ({
					city: loc.city,
					start_date: loc.startDate,
					end_date: loc.endDate || new Date().toISOString().split('T')[0],
					avg_pm25: loc.avgPM25
				}))
			},
			options: {
				max_graph_depth: 5,
				include_genetic_modifiers: true
			}
		};

		try {
			// Submit request to queue it for SSE processing
			const response = await fetch('http://localhost:8000/api/v1/submit_request', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
				},
				body: JSON.stringify(request)
			});

			if (!response.ok) {
				throw new Error('Failed to submit request');
			}

			const { request_id } = await response.json();
			currentRequestId = request_id;

			// Show progress stream
			showProgressStream = true;
			isLoading.set(true);
			error.set(null);

		} catch (err: any) {
			error.set(err.message || 'Failed to submit query');
		}
	}

	function handleProgressComplete(data: any) {
		// Hide progress stream
		showProgressStream = false;
		isLoading.set(false);

		// Update state with results
		if (data.causal_graph) {
			causalGraph.set(data.causal_graph);
		}
		if (data.explanations) {
			keyInsights.set(data.explanations);
		}
		if (data.insights) {
			causalInsightsData = data.insights;
		}
		if (currentRequestId) {
			currentGraphId = `graph-${currentRequestId}`;
		}

		// Switch to insights tab if available, otherwise graph
		selectedTab = data.insights ? 'insights' : 'graph';
	}

	function handleProgressError(errorMsg: string) {
		// Hide progress stream
		showProgressStream = false;
		isLoading.set(false);

		// Set error
		error.set(errorMsg);
	}
</script>

<div class="min-h-screen bg-gray-50">
	<!-- Header -->
	<header class="bg-white border-b border-gray-200">
		<div class="container mx-auto px-4 py-6">
			<div class="flex items-center justify-between">
				<div>
					<h1 class="text-3xl font-bold text-gray-900">Aeon Cascade</h1>
					<p class="text-lg font-semibold text-primary-600 mt-1">Mechanism Explorer for Informed Health Decisions</p>
					<p class="text-sm text-gray-600 mt-1">Validated biological mechanisms from INDRA bio-ontology (47,000+ pathways)</p>
				</div>
				<div class="flex items-center space-x-2 text-sm text-gray-500">
					<span>296K entities • 465K relationships • INDRA validated</span>
				</div>
			</div>

			<!-- Compact Notice -->
			<div class="mt-4 bg-blue-50 border border-blue-200 rounded-lg p-3">
				<p class="text-xs text-blue-800">
					<strong>Research tool:</strong> Shows literature-backed mechanisms, not medical advice.
					Population biology ≠ personalized prediction. Monitor your response with healthcare providers.
				</p>
			</div>
		</div>
	</header>

	<!-- Main Content -->
	<main class="container mx-auto px-4 py-8">
		<!-- Persona Selector -->
		<section class="mb-8">
			<h2 class="text-xl font-semibold text-gray-900 mb-4">Select User Persona</h2>
			<PersonaSelector />
		</section>

		{#if $selectedPersona}
			<!-- Genetic Biomarkers -->
			<section class="mb-8">
				<h2 class="text-xl font-semibold text-gray-900 mb-4">
					Genetic Profile: {$selectedPersona.name}
				</h2>
				<GeneticBiomarkers persona={$selectedPersona} />
			</section>

			<!-- Biomarker Timeline -->
			{#if $selectedPersona.biomarkerHistory && $selectedPersona.biomarkerHistory.length > 0}
				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">
						Biomarker History & Interventions
					</h2>
					<BiomarkerTimeline persona={$selectedPersona} />
				</section>
			{/if}

			<!-- Tab Navigation -->
			<div class="border-b border-gray-200 mb-6">
				<nav class="flex space-x-8">
					<button
						onclick={() => selectedTab = 'query'}
						class="pb-3 text-sm font-medium border-b-2 {selectedTab === 'query'
							? 'text-primary-600 border-primary-600'
							: 'text-gray-500 border-transparent hover:text-gray-700'}"
					>
						Query Builder
					</button>
					<button
						onclick={() => selectedTab = 'graph'}
						disabled={!$causalGraph}
						class="pb-3 text-sm font-medium border-b-2 {selectedTab === 'graph'
							? 'text-primary-600 border-primary-600'
							: 'text-gray-500 border-transparent hover:text-gray-700'} disabled:text-gray-400 disabled:cursor-not-allowed"
					>
						Causal Graph
					</button>
					<button
						onclick={() => selectedTab = 'interventions'}
						disabled={!$causalGraph}
						class="pb-3 text-sm font-medium border-b-2 {selectedTab === 'interventions'
							? 'text-primary-600 border-primary-600'
							: 'text-gray-500 border-transparent hover:text-gray-700'} disabled:text-gray-400 disabled:cursor-not-allowed"
					>
						Intervention Planning
					</button>
					<button
						onclick={() => selectedTab = 'insights'}
						disabled={!causalInsightsData}
						class="pb-3 text-sm font-medium border-b-2 {selectedTab === 'insights'
							? 'text-primary-600 border-primary-600'
							: 'text-gray-500 border-transparent hover:text-gray-700'} disabled:text-gray-400 disabled:cursor-not-allowed"
					>
						Causal Insights
					</button>
					<button
						onclick={() => selectedTab = 'upload'}
						class="pb-3 text-sm font-medium border-b-2 {selectedTab === 'upload'
							? 'text-primary-600 border-primary-600'
							: 'text-gray-500 border-transparent hover:text-gray-700'}"
					>
						Data Upload
					</button>
				</nav>
			</div>

			<!-- Error Display -->
			{#if $error}
				<div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
					<div class="flex items-start">
						<svg class="w-5 h-5 text-red-600 mr-2 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
							<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"></path>
						</svg>
						<div>
							<h3 class="text-sm font-semibold text-red-800">Error</h3>
							<p class="text-sm text-red-700 mt-1">{$error}</p>
						</div>
					</div>
				</div>
			{/if}

			<!-- Progress Stream -->
			{#if showProgressStream && currentRequestId}
				<ProgressStream
					requestId={currentRequestId}
					onComplete={handleProgressComplete}
					onError={handleProgressError}
				/>
			{/if}

			<!-- Tab Content -->
			{#if selectedTab === 'query' && !showProgressStream}
				<QueryBuilder on:submit={handleQuerySubmit} />
			{:else if selectedTab === 'graph'}
				<div class="space-y-6">
					<CausalGraph />

					{#if $keyInsights && $keyInsights.length > 0}
						<div class="bg-white rounded-lg border border-gray-200 p-6">
							<h4 class="text-md font-semibold text-gray-900 mb-3">Key Insights</h4>
							<ul class="space-y-2">
								{#each $keyInsights as insight}
									<li class="text-sm text-gray-700">• {insight}</li>
								{/each}
							</ul>
						</div>
					{/if}

					<!-- Temporal Cascade: Timeline Visualization -->
					<TemporalCascade />

					<!-- Graph Analysis: Feedback Loops & Convergent Nodes -->
					<GraphAnalysis graphId={currentGraphId} />
				</div>
			{:else if selectedTab === 'interventions'}
				<InterventionPlanner graphId={currentGraphId} />
			{:else if selectedTab === 'insights'}
				<CausalInsights insights={causalInsightsData} />
			{:else if selectedTab === 'upload'}
				<FileUploader />
			{/if}
		{:else}
			<div class="bg-white rounded-lg border border-gray-200 p-12 text-center">
				<svg class="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path>
				</svg>
				<h3 class="text-lg font-semibold text-gray-900 mb-2">No Persona Selected</h3>
				<p class="text-gray-600">Select a user persona above to begin exploring causal pathways.</p>
			</div>
		{/if}
	</main>

	<!-- Disclaimer Section -->
	<section id="disclaimer" class="bg-gray-100 border-t border-gray-300 mt-16">
		<div class="container mx-auto px-4 py-6">
			<div class="max-w-4xl mx-auto">
				<div class="bg-white rounded-lg border border-gray-300 p-4">
					<p class="text-sm text-gray-700 mb-3">
						<strong>Disclaimer:</strong> This tool displays validated biological mechanisms from peer-reviewed literature (INDRA bio-ontology).
						Pathways shown represent population-level biology, not personalized medical predictions.
					</p>
					<p class="text-xs text-gray-600">
						<strong>Not medical advice.</strong> Mechanisms exist in humans (evidence: paper counts, belief scores), but individual response varies by genetics, microbiome, and environment.
						Consult healthcare providers and monitor your biomarkers to validate response.
					</p>
					<p class="text-xs text-gray-500 mt-2">
						Clinical Decision Support tool exempt under 21 USC § 360j(o)(1)(E). Displays medical information for independent review; does not diagnose or prescribe.
					</p>
				</div>
			</div>
		</div>
	</section>

	<!-- Footer -->
	<footer class="bg-white border-t border-gray-200">
		<div class="container mx-auto px-4 py-6">
			<div class="flex flex-col md:flex-row items-center justify-between space-y-4 md:space-y-0">
				<p class="text-sm text-gray-500">
					Aeon Cascade © 2025 • Mechanism Explorer for Informed Health Decisions
				</p>
				<div class="flex space-x-6 text-sm">
					<a href="/about" class="text-gray-600 hover:text-primary-600 transition-colors">About</a>
					<a href="/terms" class="text-gray-600 hover:text-primary-600 transition-colors">Terms of Service</a>
					<a href="/privacy" class="text-gray-600 hover:text-primary-600 transition-colors">Privacy Policy</a>
				</div>
			</div>
			<p class="text-xs text-gray-400 text-center mt-4">
				Transparency > Paternalism | Informed Decisions > Blind Adherence | Population Biology ≠ You
			</p>
			<p class="text-xs text-gray-400 text-center mt-1">
				Built with SvelteKit, INDRA Bio-Ontology, and AWS Bedrock
			</p>
		</div>
	</footer>
</div>
