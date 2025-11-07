<script lang="ts">
	import Card from '$lib/components/ui/Card.svelte';
</script>

<svelte:head>
	<title>Privacy Policy - Aeon Cascade</title>
</svelte:head>

<div class="min-h-screen bg-gray-50">
	<header class="bg-white border-b border-gray-200">
		<div class="container mx-auto px-4 py-6">
			<div class="flex items-center justify-between">
				<div>
					<h1 class="text-3xl font-bold text-gray-900">Privacy Policy</h1>
					<p class="text-sm text-gray-600 mt-1">How we collect, use, and protect your data</p>
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

				<div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
					<p class="text-sm text-blue-900 font-semibold mb-2">Privacy Commitment</p>
					<p class="text-sm text-blue-800">
						Aeon Cascade is a <strong>research and educational tool</strong> focused on displaying biological mechanisms.
						We collect minimal data necessary for system operation and <strong>do NOT share personal health information</strong>
						with third parties for commercial purposes.
					</p>
				</div>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">1. Data We Collect</h2>

					<h3 class="text-lg font-semibold text-gray-900 mb-3">1.1 Query Data</h3>
					<p class="text-gray-700 mb-3">When you use Aeon Cascade, we collect:</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>
							<strong>Query text</strong>: Your health-related questions (e.g., "How does PM2.5 affect CRP?")
						</li>
						<li>
							<strong>Timestamp</strong>: When the query was submitted
						</li>
						<li>
							<strong>Session ID</strong>: Anonymous identifier for grouping related queries
						</li>
					</ul>
					<p class="text-gray-700 mt-3">
						<strong>Purpose:</strong> System operation, result caching, performance optimization
					</p>

					<h3 class="text-lg font-semibold text-gray-900 mb-3 mt-6">1.2 Optional User Context (If Provided)</h3>
					<p class="text-gray-700 mb-3">Users may optionally provide:</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>
							<strong>Genetic variants</strong>: e.g., "GSTM1 null" (for pathway modifier analysis)
						</li>
						<li>
							<strong>Current biomarkers</strong>: e.g., "CRP: 5.2 mg/L" (for baseline comparison)
						</li>
						<li>
							<strong>Location history</strong>: e.g., "San Francisco, 2024-2025" (for environmental exposure analysis)
						</li>
					</ul>
					<p class="text-gray-700 mt-3">
						<strong>Storage:</strong> Local browser storage only (not sent to server unless explicitly submitted in query)
					</p>
					<p class="text-gray-700 mt-2">
						<strong>Control:</strong> You can clear this data at any time via browser settings
					</p>

					<h3 class="text-lg font-semibold text-gray-900 mb-3 mt-6">1.3 Technical Data</h3>
					<p class="text-gray-700 mb-3">For system reliability and error tracking:</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>
							<strong>Browser type and version</strong>: For compatibility testing
						</li>
						<li>
							<strong>IP address</strong>: For rate limiting and abuse prevention (anonymized after 30 days)
						</li>
						<li>
							<strong>Error logs</strong>: Technical errors encountered (no personal data)
						</li>
						<li>
							<strong>Response times</strong>: For performance monitoring
						</li>
					</ul>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">2. Data We DO NOT Collect</h2>
					<div class="bg-green-50 border border-green-200 rounded-lg p-4">
						<ul class="list-none text-gray-800 space-y-2">
							<li>❌ <strong>No account creation required</strong> - System is anonymous by design</li>
							<li>❌ <strong>No email addresses or contact information</strong> (unless you contact support)</li>
							<li>❌ <strong>No medical records or diagnostic data</strong></li>
							<li>❌ <strong>No personally identifiable information (PII)</strong></li>
							<li>❌ <strong>No cookies for advertising or tracking</strong></li>
							<li>❌ <strong>No third-party analytics trackers</strong> (Google Analytics, Facebook Pixel, etc.)</li>
						</ul>
					</div>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">3. How We Use Your Data</h2>
					<p class="text-gray-700 mb-3">Data collected is used ONLY for:</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>
							<strong>Processing queries</strong>: Fetching causal pathways from INDRA database
						</li>
						<li>
							<strong>Result caching</strong>: Reducing latency for common queries (cache expires after 24 hours)
						</li>
						<li>
							<strong>Error debugging</strong>: Identifying and fixing technical issues
						</li>
						<li>
							<strong>System improvements</strong>: Aggregate usage statistics (anonymized)
						</li>
						<li>
							<strong>Abuse prevention</strong>: Rate limiting, bot detection
						</li>
					</ul>
					<p class="text-gray-700 mt-3">
						<strong>We do NOT:</strong>
					</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>Sell or rent your data to third parties</li>
						<li>Use your data for advertising or marketing</li>
						<li>Share individual queries with external researchers without explicit consent</li>
						<li>Profile users for behavioral targeting</li>
					</ul>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">4. Data Sharing and Third Parties</h2>

					<h3 class="text-lg font-semibold text-gray-900 mb-3">4.1 Third-Party Services</h3>
					<p class="text-gray-700 mb-3">
						Aeon Cascade uses the following external services for system operation:
					</p>
					<ul class="list-disc list-inside text-gray-700 space-y-3 ml-4">
						<li>
							<strong>INDRA Bio-Ontology API</strong> (Harvard Medical School)
							<ul class="list-circle list-inside text-gray-600 text-sm ml-6 mt-1">
								<li>Purpose: Fetch causal pathways from scientific literature</li>
								<li>Data shared: Entity names only (e.g., "CRP", "PM2.5"), NOT personal health data</li>
								<li>Privacy policy: <a href="https://indra.bio" class="text-primary-600 hover:text-primary-700" target="_blank" rel="noopener noreferrer">https://indra.bio</a></li>
							</ul>
						</li>
						<li>
							<strong>AWS Bedrock (Claude Sonnet 4.5)</strong> (Amazon Web Services)
							<ul class="list-circle list-inside text-gray-600 text-sm ml-6 mt-1">
								<li>Purpose: Generate human-readable explanations of biological mechanisms</li>
								<li>Data shared: Query text and INDRA results (anonymized, no user identifiers)</li>
								<li>Privacy policy: <a href="https://aws.amazon.com/privacy/" class="text-primary-600 hover:text-primary-700" target="_blank" rel="noopener noreferrer">AWS Privacy Notice</a></li>
							</ul>
						</li>
						<li>
							<strong>IQAir API</strong> (optional, if environmental queries enabled)
							<ul class="list-circle list-inside text-gray-600 text-sm ml-6 mt-1">
								<li>Purpose: Fetch real-time air quality data for location-based queries</li>
								<li>Data shared: City names only (e.g., "San Francisco"), NOT user identities</li>
								<li>Privacy policy: <a href="https://www.iqair.com/privacy" class="text-primary-600 hover:text-primary-700" target="_blank" rel="noopener noreferrer">IQAir Privacy</a></li>
							</ul>
						</li>
					</ul>

					<h3 class="text-lg font-semibold text-gray-900 mb-3 mt-6">4.2 Legal Disclosures</h3>
					<p class="text-gray-700">
						We may disclose data if required by law (subpoena, court order) or to protect system security
						(e.g., preventing abuse, cyberattacks). Such disclosures will be limited to the minimum necessary.
					</p>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">5. Data Retention</h2>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>
							<strong>Query data</strong>: Retained for 90 days, then anonymized (entity names preserved for research, user identifiers removed)
						</li>
						<li>
							<strong>Result cache</strong>: Expires after 24 hours (common pathways) or 1 hour (user-specific queries)
						</li>
						<li>
							<strong>Error logs</strong>: Retained for 30 days, then deleted
						</li>
						<li>
							<strong>IP addresses</strong>: Anonymized after 30 days (last octet removed)
						</li>
					</ul>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">6. Data Security</h2>
					<p class="text-gray-700 mb-3">
						We implement industry-standard security measures:
					</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>
							<strong>HTTPS encryption</strong>: All data transmission encrypted via TLS 1.3
						</li>
						<li>
							<strong>Database encryption</strong>: At-rest encryption for stored queries (AES-256)
						</li>
						<li>
							<strong>Access controls</strong>: Role-based access, minimal privilege principle
						</li>
						<li>
							<strong>Regular security audits</strong>: Penetration testing, vulnerability scanning
						</li>
						<li>
							<strong>No plaintext storage</strong>: Personal health context encrypted before storage
						</li>
					</ul>
					<p class="text-gray-700 mt-3">
						<strong>Important:</strong> No system is 100% secure. If you have concerns about data sensitivity,
						avoid entering identifiable personal health information in queries.
					</p>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">7. Your Rights</h2>
					<p class="text-gray-700 mb-3">
						Depending on your jurisdiction (e.g., GDPR in EU, CCPA in California), you may have rights to:
					</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>
							<strong>Access your data</strong>: Request a copy of data associated with your session ID
						</li>
						<li>
							<strong>Delete your data</strong>: Request deletion of queries and results (subject to legal retention requirements)
						</li>
						<li>
							<strong>Correct inaccuracies</strong>: Update or correct stored information
						</li>
						<li>
							<strong>Object to processing</strong>: Opt out of non-essential data uses (e.g., research analytics)
						</li>
						<li>
							<strong>Data portability</strong>: Export your data in machine-readable format (JSON)
						</li>
					</ul>
					<p class="text-gray-700 mt-3">
						To exercise these rights, contact: <a href="mailto:privacy@aeoncascade.com" class="text-primary-600 hover:text-primary-700">privacy@aeoncascade.com</a>
					</p>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">8. Children's Privacy</h2>
					<div class="bg-yellow-50 border-l-4 border-yellow-400 p-4">
						<p class="text-yellow-900 font-semibold mb-2">⚠️ Age Restriction</p>
						<p class="text-sm text-yellow-800">
							Aeon Cascade is NOT intended for children under 18. We do not knowingly collect data from minors.
							If you are under 18, please do not use this system without parental supervision.
						</p>
					</div>
					<p class="text-gray-700 mt-3">
						If we discover that a child under 18 has submitted queries, we will delete associated data promptly.
						Parents/guardians can contact us at <a href="mailto:privacy@aeoncascade.com" class="text-primary-600 hover:text-primary-700">privacy@aeoncascade.com</a> to request deletion.
					</p>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">9. International Data Transfers</h2>
					<p class="text-gray-700 mb-3">
						Aeon Cascade is hosted in the United States. If you access the system from outside the US:
					</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>Your data may be transferred to and stored in US servers</li>
						<li>US privacy laws may differ from your jurisdiction</li>
						<li>We comply with applicable international privacy frameworks (GDPR adequacy mechanisms)</li>
					</ul>
					<p class="text-gray-700 mt-3">
						By using Aeon Cascade, you consent to cross-border data transfers as described.
					</p>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">10. Cookies and Tracking</h2>
					<p class="text-gray-700 mb-3">
						<strong>We use minimal cookies</strong> for essential functionality only:
					</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>
							<strong>Session cookie</strong>: Temporary identifier for grouping related queries (expires when browser closes)
						</li>
						<li>
							<strong>Preference cookie</strong>: Remembers UI settings (theme, layout) - optional, can be disabled
						</li>
					</ul>
					<p class="text-gray-700 mt-3">
						<strong>We do NOT use:</strong>
					</p>
					<ul class="list-disc list-inside text-gray-700 space-y-1 ml-4">
						<li>Third-party advertising cookies (Google Ads, Facebook Pixel)</li>
						<li>Cross-site tracking cookies</li>
						<li>Analytics cookies (no Google Analytics, Mixpanel, etc.)</li>
					</ul>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">11. Research Use of Anonymized Data</h2>
					<p class="text-gray-700 mb-3">
						We may use <strong>anonymized, aggregated query data</strong> for research purposes:
					</p>
					<ul class="list-disc list-inside text-gray-700 space-y-2 ml-4">
						<li>
							<strong>Example research questions:</strong> "What are the most common biomarker queries?"
							"Which pathways have highest user interest?"
						</li>
						<li>
							<strong>Anonymization process:</strong> All user identifiers (session IDs, IP addresses) removed,
							only entity names and query patterns retained
						</li>
						<li>
							<strong>Publication:</strong> Research findings may be published in academic papers, but individual
							queries will never be disclosed
						</li>
					</ul>
					<p class="text-gray-700 mt-3">
						If you object to research use, contact <a href="mailto:privacy@aeoncascade.com" class="text-primary-600 hover:text-primary-700">privacy@aeoncascade.com</a> to opt out.
					</p>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">12. Changes to This Policy</h2>
					<p class="text-gray-700">
						We may update this Privacy Policy to reflect system changes or legal requirements. Material changes
						will be posted on this page with an updated "Last Updated" date. For significant changes affecting
						data use, we will notify users via homepage banner.
					</p>
				</section>

				<section class="mb-8">
					<h2 class="text-xl font-semibold text-gray-900 mb-4">13. Contact Information</h2>
					<p class="text-gray-700 mb-3">
						For privacy questions, data access requests, or security concerns:
					</p>
					<ul class="list-none text-gray-700 space-y-2">
						<li>
							<strong>Email:</strong> <a href="mailto:privacy@aeoncascade.com" class="text-primary-600 hover:text-primary-700">privacy@aeoncascade.com</a>
						</li>
						<li>
							<strong>Data Protection Officer:</strong> <a href="mailto:dpo@aeoncascade.com" class="text-primary-600 hover:text-primary-700">dpo@aeoncascade.com</a>
						</li>
						<li>
							<strong>Security issues:</strong> <a href="mailto:security@aeoncascade.com" class="text-primary-600 hover:text-primary-700">security@aeoncascade.com</a>
						</li>
					</ul>
				</section>

				<div class="border-t border-gray-300 pt-6 mt-8">
					<p class="text-sm text-gray-600">
						By using Aeon Cascade, you acknowledge that you have read and understood this Privacy Policy.
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
