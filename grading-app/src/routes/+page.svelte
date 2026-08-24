<script>
    import { onMount, tick } from 'svelte';
    import { fade, fly, slide } from 'svelte/transition';

    let entry = null;
    let loading = true;
    let rating = 0;
    let timeClass = null; // time: 'am','pm','ambiguous' | date: 'exact','relative','ambiguous'
    let error = null;
    let stats = { total_entries: 0, voted_entries: 0, average_rating: 0 };
    let hasVotedRating = false;
    let snippetContainer;
    let dataset = 'time'; // 'time' | 'date'
    let appMode = 'entry'; // 'entry' | 'bookReview'
    
    // Time Correction
    let correctedTime = '';
    let isEditingTime = false;
    let isMetaExpanded = false;

    // Book spam review mode
    let spamThreshold = 50;
    let sampleSize = 50;
    let suspectBooks = [];
    let suspectBooksLoading = false;
    let suspectBooksError = null;
    let currentBookIndex = 0;
    let booksReviewed = 0;
    let bookSample = [];
    let bookSampleLoading = false;
    let bookSampleError = null;
    let bookDeleteStats = { books: 0, entries: 0, votes: 0 };
    let isBookTitleExpanded = false;

    const CLASS_OPTIONS = {
        time: ['am', 'pm', 'ambiguous'],
        date: ['exact', 'relative', 'ambiguous']
    };
    function getClassOptions() {
        return dataset === 'date' ? CLASS_OPTIONS.date : CLASS_OPTIONS.time;
    }

    function getExpectedValue(currentEntry) {
        if (!currentEntry) return '';
        if (dataset === 'date') return currentEntry.valid_dates ? currentEntry.valid_dates[0] : '';
        return currentEntry.valid_times ? currentEntry.valid_times[0] : '';
    }

    async function fetchStats() {
        try {
            const res = await fetch(`/api/stats?dataset=${dataset}`);
            if (res.ok) {
                stats = await res.json();
            }
        } catch (e) {
            console.error("Stats fetch failed", e);
        }
    }

    async function fetchEntry() {
        if (appMode !== 'entry') return;
        loading = true;
        entry = null;
        rating = 0;
        timeClass = null;
        error = null;
        hasVotedRating = false;
        isEditingTime = false;
        isMetaExpanded = false;
        correctedTime = '';
        
        try {
            const res = await fetch(`/api/entries?dataset=${dataset}`);
            if (res.ok) {
                const data = await res.json();
                if (data && !data.error) {
                    entry = data;
                    if (dataset === 'time') {
                        if (entry.ai_am_pm && ['am', 'pm', 'ambiguous'].includes(entry.ai_am_pm.toLowerCase())) {
                            timeClass = entry.ai_am_pm.toLowerCase();
                        } else if (entry.valid_times && entry.valid_times.length === 1) {
                            const hour = parseInt(entry.valid_times[0].split(':')[0], 10);
                            if (!isNaN(hour)) {
                                timeClass = hour >= 12 ? 'pm' : 'am';
                            }
                        }
                    }
                    await tick();
                    if (snippetContainer) {
                        snippetContainer.scrollTop = 0;
                    }
                } else {
                    error = data?.error || "No entry found";
                }
            } else {
                error = "Failed to fetch";
            }
        } catch (e) {
            error = e.message;
        } finally {
            loading = false;
        }
    }

    async function fetchSuspectBooks() {
        suspectBooksLoading = true;
        suspectBooksError = null;
        suspectBooks = [];
        currentBookIndex = 0;
        booksReviewed = 0;
        bookSample = [];
        bookSampleError = null;
        isBookTitleExpanded = false;
        try {
            const params = new URLSearchParams({
                dataset,
                threshold: String(spamThreshold)
            });
            const res = await fetch(`/api/book-review/books?${params.toString()}`);
            const data = await res.json();
            if (!res.ok) throw new Error(data?.error || 'Failed to load suspect books');
            suspectBooks = data.books || [];
            await fetchCurrentBookSample();
        } catch (e) {
            suspectBooksError = e.message;
        } finally {
            suspectBooksLoading = false;
        }
    }

    async function fetchCurrentBookSample() {
        bookSample = [];
        bookSampleError = null;
        const current = suspectBooks[currentBookIndex];
        if (!current) return;
        bookSampleLoading = true;
        try {
            const params = new URLSearchParams({
                dataset,
                title: current.title,
                limit: String(sampleSize)
            });
            const res = await fetch(`/api/book-review/sample?${params.toString()}`);
            const data = await res.json();
            if (!res.ok) throw new Error(data?.error || 'Failed to load sample');
            bookSample = data.sample || [];
        } catch (e) {
            bookSampleError = e.message;
        } finally {
            bookSampleLoading = false;
        }
    }

    function advanceBookReview() {
        booksReviewed += 1;
        currentBookIndex += 1;
        isBookTitleExpanded = false;
        fetchCurrentBookSample();
    }

    function keepCurrentBook() {
        if (!currentBook) return;
        advanceBookReview();
    }

    async function deleteCurrentBook() {
        if (!currentBook) return;
        const confirmed = window.confirm(
            `Delete all ${currentBook.entry_count} entries for "${currentBook.title}" in ${dataset} dataset?`
        );
        if (!confirmed) return;

        bookSampleLoading = true;
        bookSampleError = null;
        try {
            const res = await fetch('/api/book-review/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dataset, title: currentBook.title })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data?.error || 'Delete failed');
            bookDeleteStats = {
                books: bookDeleteStats.books + 1,
                entries: bookDeleteStats.entries + (data.deleted_entries || 0),
                votes: bookDeleteStats.votes + (data.deleted_votes || 0)
            };
            advanceBookReview();
        } catch (e) {
            bookSampleError = e.message;
        } finally {
            bookSampleLoading = false;
        }
    }

    async function submitVote(isDeny = false) {
        if (!entry) return;
        
        if (isDeny) {
            // No validation needed for deny
        } else {
            if (!timeClass) {
                alert(dataset === 'date' ? "Please select Exact, Relative, or Ambiguous" : "Please select AM, PM, or Ambiguous");
                return;
            }
            if (rating === 0) {
                alert("Please rate the quote (1-5 stars) or use Deny");
                return;
            }
        }
        
        const finalRating = isDeny ? 0 : rating;
        const finalTimeClass = isDeny ? (timeClass || 'ambiguous') : timeClass;
        
        // Use corrected time if provided and editing was active or value exists
        const expectedValue = getExpectedValue(entry);
        const finalTime = (correctedTime && correctedTime !== expectedValue) ? correctedTime : null;

        const voteData = { 
            entry_id: entry.id, 
            rating: finalRating, 
            am_pm: finalTimeClass,
            corrected_time: finalTime,
            class_value: finalTimeClass,
            corrected_value: finalTime,
            dataset
        };
        
        fetchEntry();
        
        try {
            await fetch('/api/vote', {
                method: 'POST',
                body: JSON.stringify(voteData),
                headers: { 'Content-Type': 'application/json' }
            });
            fetchStats();
        } catch (e) {
            console.error("Vote failed silently", e);
        }
    }
    
    function setTimeClass(val) {
        timeClass = val;
    }
    
    function setRating(val) {
        rating = val;
        hasVotedRating = true;
    }

    function formatTimeForInput(timeStr) {
        if (!timeStr) return '';
        if (dataset === 'date') return timeStr;
        // Ensure HH:MM format (pad hour with 0 if needed)
        const parts = timeStr.split(':');
        if (parts.length === 2) {
            return `${parts[0].padStart(2, '0')}:${parts[1]}`;
        }
        return timeStr;
    }

    onMount(() => {
        const params = new URLSearchParams(window.location.search);
        const requestedDataset = params.get('dataset');
        if (requestedDataset === 'date') {
            dataset = 'date';
        }
        if (params.get('mode') === 'book') {
            appMode = 'bookReview';
        }
        fetchStats();
        if (appMode === 'bookReview') {
            fetchSuspectBooks();
        } else {
            fetchEntry();
        }
    });

    $: progress = stats.total_entries > 0 ? (stats.voted_entries / stats.total_entries) * 100 : 0;
    $: bookTotal = suspectBooks.length;
    $: bookProgress = bookTotal > 0 ? (booksReviewed / bookTotal) * 100 : 0;
    $: currentBook = suspectBooks[currentBookIndex] || null;
    $: currentBookLink = (bookSample.find((s) => s?.link) || null)?.link || null;

    function setDataset(nextDataset) {
        if (nextDataset !== 'time' && nextDataset !== 'date') return;
        if (dataset === nextDataset) return;
        dataset = nextDataset;
        const params = new URLSearchParams(window.location.search);
        params.set('dataset', nextDataset);
        params.set('mode', appMode === 'bookReview' ? 'book' : 'entry');
        window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`);
        if (appMode === 'bookReview') {
            fetchSuspectBooks();
        } else {
            fetchStats();
            fetchEntry();
        }
    }

    function setAppMode(nextMode) {
        if (nextMode !== 'entry' && nextMode !== 'bookReview') return;
        if (appMode === nextMode) return;
        appMode = nextMode;
        const params = new URLSearchParams(window.location.search);
        params.set('dataset', dataset);
        params.set('mode', appMode === 'bookReview' ? 'book' : 'entry');
        window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`);
        if (appMode === 'bookReview') {
            fetchSuspectBooks();
        } else {
            fetchStats();
            fetchEntry();
        }
    }
</script>

<style>
    :global(.marked) {
        font-weight: 900;
        text-decoration: underline;
        color: #000;
        background-color: #fef08a;
        padding: 0 2px;
        border-radius: 2px;
    }
</style>

<div class="min-h-screen bg-gray-100 flex flex-col items-center p-4">
    <!-- Sticky Stats Bar -->
    <div class="sticky top-0 z-50 w-full max-w-md mb-4 bg-white rounded-xl shadow-md p-4 border-b-2 border-blue-500">
        <div class="grid grid-cols-2 gap-2 mb-3">
            <button
                class="py-2 text-xs font-bold rounded-lg uppercase border-2 transition-all {appMode === 'entry' ? 'border-blue-600 bg-blue-600 text-white' : 'border-gray-200 bg-white text-gray-500'}"
                on:click={() => setAppMode('entry')}
            >
                Entry Grader
            </button>
            <button
                class="py-2 text-xs font-bold rounded-lg uppercase border-2 transition-all {appMode === 'bookReview' ? 'border-amber-600 bg-amber-500 text-white' : 'border-gray-200 bg-white text-gray-500'}"
                on:click={() => setAppMode('bookReview')}
            >
                Book Review
            </button>
        </div>
        <div class="grid grid-cols-2 gap-2 mb-3">
            <button
                class="py-2 text-xs font-bold rounded-lg uppercase border-2 transition-all {dataset === 'time' ? 'border-blue-600 bg-blue-600 text-white' : 'border-gray-200 bg-white text-gray-500'}"
                on:click={() => setDataset('time')}
            >
                Time Mode
            </button>
            <button
                class="py-2 text-xs font-bold rounded-lg uppercase border-2 transition-all {dataset === 'date' ? 'border-blue-600 bg-blue-600 text-white' : 'border-gray-200 bg-white text-gray-500'}"
                on:click={() => setDataset('date')}
            >
                Date Mode
            </button>
        </div>
        {#if appMode === 'entry'}
            <div class="flex justify-between text-sm font-bold text-gray-700 mb-2">
                <span>Progress: {stats.voted_entries} / {stats.total_entries}</span>
                <span>{progress.toFixed(2)}%</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-3 mb-2">
                <div class="bg-blue-600 h-3 rounded-full transition-all duration-500" style="width: {progress}%"></div>
            </div>
            <div class="flex justify-between items-center text-xs text-gray-500">
                <span>Avg Rating: <span class="font-bold text-yellow-600">{stats.average_rating.toFixed(1)} ★</span></span>
                <span class="italic">0 ★ = Denied</span>
            </div>
        {:else}
            <div class="flex justify-between text-sm font-bold text-gray-700 mb-2">
                <span>Books graded: {booksReviewed} / {bookTotal}</span>
                <span>{bookProgress.toFixed(2)}%</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-3 mb-2">
                <div class="bg-amber-500 h-3 rounded-full transition-all duration-500" style="width: {bookProgress}%"></div>
            </div>
            <div class="flex justify-between items-center text-xs text-gray-500 gap-2">
                <span>Threshold: {spamThreshold}+ matches</span>
                <span>Sample: {sampleSize}</span>
                <span class="truncate">Deleted: {bookDeleteStats.books} books</span>
            </div>
        {/if}
    </div>

    <div class="relative w-full max-w-md flex-1 mb-20" style="min-height: 500px;">
        {#if appMode === 'bookReview'}
            {#if suspectBooksLoading}
                <div class="absolute inset-0 flex items-center justify-center bg-white rounded-xl shadow-xl">
                    <p class="text-gray-500 animate-pulse">Loading suspect books...</p>
                </div>
            {:else if suspectBooksError}
                <div class="absolute inset-0 flex flex-col items-center justify-center bg-white rounded-xl shadow-xl p-6 text-center">
                    <p class="text-red-500 mb-4 font-bold">{suspectBooksError}</p>
                    <button on:click={fetchSuspectBooks} class="px-6 py-2 bg-amber-500 text-white rounded-lg shadow">Retry</button>
                </div>
            {:else if !currentBook}
                <div class="absolute inset-0 flex flex-col items-center justify-center bg-white rounded-xl shadow-xl p-6 text-center">
                    <p class="text-gray-700 mb-2 font-bold">Book review queue complete</p>
                    <p class="text-xs text-gray-500 mb-4">Only books with more than {spamThreshold} entries are included.</p>
                    <button on:click={fetchSuspectBooks} class="px-6 py-2 bg-amber-500 text-white rounded-lg shadow">Reload Queue</button>
                </div>
            {:else}
                <div class="absolute inset-0 bg-white rounded-xl shadow-2xl overflow-hidden flex flex-col">
                    <div class="bg-gray-800 text-white p-4 shrink-0 space-y-2">
                        <div class="flex items-start justify-between gap-3">
                            <div class="min-w-0">
                                <div class="text-[10px] uppercase tracking-widest text-amber-300 font-bold">Book Spam Review</div>
                                <button
                                    type="button"
                                    class="w-full text-left font-bold leading-tight text-sm truncate hover:text-amber-200 transition-colors"
                                    on:click={() => isBookTitleExpanded = !isBookTitleExpanded}
                                    title="Click to expand full title"
                                >
                                    {currentBook.title}
                                </button>
                                {#if isBookTitleExpanded}
                                    <div class="mt-2 p-2 rounded bg-gray-700/70 border border-gray-600 text-xs text-gray-100 break-words">
                                        {currentBook.title}
                                    </div>
                                {/if}
                                <div class="text-xs text-gray-300">
                                    {currentBook.entry_count} matches in {dataset === 'date' ? 'Date' : 'Time'} DB
                                </div>
                            </div>
                            <div class="shrink-0 flex gap-2">
                                {#if currentBookLink}
                                    <a
                                        href={currentBookLink}
                                        target="_blank"
                                        class="px-3 py-1.5 rounded-md bg-blue-600 hover:bg-blue-500 text-xs font-bold"
                                        title="Open a source page for this book"
                                    >
                                        Go to Book
                                    </a>
                                {/if}
                                <button
                                    on:click={fetchCurrentBookSample}
                                    class="px-3 py-1.5 rounded-md bg-gray-700 hover:bg-gray-600 text-xs font-bold"
                                    title="Load a new random sample for this title"
                                >
                                    Resample
                                </button>
                            </div>
                        </div>
                    </div>

                    <div class="flex-1 overflow-y-auto bg-gray-50/50 p-3 space-y-3">
                        {#if bookSampleLoading}
                            <div class="h-full min-h-[240px] flex items-center justify-center">
                                <p class="text-gray-500 animate-pulse">Loading sample...</p>
                            </div>
                        {:else if bookSampleError}
                            <div class="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
                                {bookSampleError}
                            </div>
                        {:else if bookSample.length === 0}
                            <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm text-yellow-800">
                                No sample rows found for this title.
                            </div>
                        {:else}
                            {#each bookSample as sample}
                                <div class="bg-white border border-gray-200 rounded-lg p-3 shadow-sm">
                                    <div class="flex items-center justify-between gap-2 mb-2 text-[11px] text-gray-500">
                                        <span class="font-mono">#{sample.id}</span>
                                        <span class="truncate">{dataset === 'date' ? sample.valid_dates : sample.valid_times}</span>
                                    </div>
                                    {#if sample.ai_rating !== null || sample.ai_reason}
                                        <div class="mb-2 p-2 bg-blue-50 border border-blue-100 rounded text-[11px] text-blue-900">
                                            <span class="font-bold mr-2">AI:</span>
                                            {#if sample.ai_rating !== null}<span class="font-semibold">{sample.ai_rating}/5</span>{/if}
                                            {#if sample.ai_reason}<span class="italic ml-1">"{sample.ai_reason}"</span>{/if}
                                        </div>
                                    {/if}
                                    <div class="prose prose-sm max-w-none text-gray-800 leading-relaxed">
                                        {@html sample.snippet}
                                    </div>
                                    <div class="mt-2 flex justify-between items-center gap-2 text-[11px] text-gray-500">
                                        <span class="truncate">{sample.author || 'Unknown author'}</span>
                                        {#if sample.link}
                                            <a href={sample.link} target="_blank" class="text-blue-600 underline shrink-0">Source</a>
                                        {/if}
                                    </div>
                                </div>
                            {/each}
                        {/if}
                    </div>

                    <div class="bg-gray-50 p-3 border-t border-gray-200 shrink-0 space-y-2">
                        <div class="flex gap-2">
                            <button
                                on:click={keepCurrentBook}
                                disabled={bookSampleLoading || !currentBook}
                                class="flex-1 py-3 rounded-lg font-bold text-emerald-700 border-2 border-emerald-100 hover:bg-emerald-50 transition-all uppercase text-xs disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                Keep Book
                            </button>
                            <button
                                on:click={deleteCurrentBook}
                                disabled={bookSampleLoading || !currentBook}
                                class="flex-1 py-3 rounded-lg font-bold text-white bg-gradient-to-r from-red-500 to-rose-600 hover:from-red-600 hover:to-rose-700 transition-all shadow-lg uppercase text-xs disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                Delete All Instances
                            </button>
                        </div>
                        <div class="text-[11px] text-gray-500 flex justify-between">
                            <span>Book {Math.min(currentBookIndex + 1, bookTotal)} of {bookTotal}</span>
                            <span>Reviewed this session: {booksReviewed}</span>
                        </div>
                    </div>
                </div>
            {/if}
        {:else if loading}
            <div class="absolute inset-0 flex items-center justify-center bg-white rounded-xl shadow-xl">
                <p class="text-gray-500 animate-pulse">Finding next quote...</p>
            </div>
        {:else if error}
             <div class="absolute inset-0 flex flex-col items-center justify-center bg-white rounded-xl shadow-xl p-6 text-center">
                <p class="text-red-500 mb-4 font-bold">{error}</p>
                <button on:click={fetchEntry} class="px-6 py-2 bg-blue-500 text-white rounded-lg shadow">Retry</button>
            </div>
        {:else if entry}
            <div in:fade={{ duration: 200 }} out:fly={{ x: -200, duration: 300 }} class="absolute inset-0 bg-white rounded-xl shadow-2xl overflow-hidden flex flex-col">
                <!-- Card Header (Pinned) -->
                <div class="bg-gray-800 text-white p-4 shrink-0 space-y-2">
                    <div class="flex items-center justify-between gap-2">
                        <div class="flex items-center min-w-0 flex-1">
                            {#if isEditingTime}
                                <input 
                                    type={dataset === 'date' ? 'text' : 'time'}
                                    bind:value={correctedTime} 
                                    placeholder={dataset === 'date' ? 'YYYY.MM.DD' : ''}
                                    class="bg-gray-700 text-white font-mono font-bold text-xl {dataset === 'date' ? 'w-44' : 'w-32'} px-2 py-1 rounded border border-gray-500 focus:outline-none focus:border-blue-400 text-center"
                                />
                                <button on:click={() => isEditingTime = false} class="ml-2 text-gray-400 hover:text-white">
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" /></svg>
                                </button>
                            {:else}
                                <button 
                                    on:click={() => { isEditingTime = true; correctedTime = formatTimeForInput(getExpectedValue(entry)); }} 
                                    class="text-2xl font-mono font-bold hover:text-blue-300 transition-colors flex items-center gap-2 group min-w-0"
                                    title={dataset === 'date' ? 'Click to correct date' : 'Click to correct time'}
                                >
                                    <span class="truncate">{getExpectedValue(entry) || (dataset === 'date' ? '????.??.??' : '??:??')}</span>
                                    <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 opacity-0 group-hover:opacity-50 transition-opacity" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                                </button>
                            {/if}
                        </div>
                        <a href={entry.link} target="_blank" class="text-xs text-blue-300 underline shrink-0">View Source</a>
                    </div>
                    {#if entry.is_re_grade}
                        <div>
                            <span class="inline-flex bg-red-500 text-white text-[10px] font-black px-2 py-1 rounded uppercase tracking-tighter animate-pulse">Re-grading</span>
                        </div>
                    {/if}
                </div>

                <!-- Scrollable Snippet Content (Middle) -->
                <div bind:this={snippetContainer} class="flex-1 p-6 overflow-y-auto flex flex-col justify-start bg-gray-50/30">
                    {#if entry.ai_rating !== null || entry.ai_reason}
                        <div class="mb-4 p-2 {entry.is_re_grade ? 'bg-red-50 border-red-200' : 'bg-blue-50 border-blue-100'} border rounded-lg text-left shadow-sm">
                            <div class="flex justify-between items-center mb-1">
                                <span class="text-[10px] font-bold {entry.is_re_grade ? 'text-red-400' : 'text-blue-400'} uppercase tracking-tight">
                                    {entry.is_re_grade ? 'AI REJECTION' : 'AI Assessment'}
                                </span>
                                {#if entry.ai_rating !== null}
                                    <span class="text-xs font-bold {entry.is_re_grade ? 'text-red-600' : 'text-blue-600'}">{entry.ai_rating}/5 ★</span>
                                {/if}
                            </div>
                            {#if entry.ai_reason}
                                <p class="text-[11px] {entry.is_re_grade ? 'text-red-800' : 'text-blue-800'} leading-tight italic">"{entry.ai_reason}"</p>
                            {/if}
                        </div>
                    {/if}
                    
                    <div class="prose prose-lg text-gray-800 text-center leading-relaxed">
                        {@html entry.snippet}
                    </div>
                </div>

                <!-- Pinned Meta Info (Collapsible) -->
                <button 
                    class="w-full text-left p-2 border-t border-gray-100 bg-white shrink-0 shadow-[0_-4px_6px_-1px_rgba(0,0,0,0.05)] z-10 hover:bg-gray-50 transition-colors"
                    on:click={() => isMetaExpanded = !isMetaExpanded}
                >
                    <div class="flex justify-between items-center">
                        <div class="truncate text-xs text-gray-700 font-semibold w-full pr-2">
                            {entry.author ? `${entry.author} - ` : ''}{entry.title}
                        </div>
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-gray-400 shrink-0 transform transition-transform duration-200 {isMetaExpanded ? 'rotate-180' : ''}" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7" />
                        </svg>
                    </div>

                    {#if isMetaExpanded}
                        <div class="mt-2 text-center border-t border-gray-100 pt-2" transition:slide={{ duration: 200 }}>
                            <p class="font-bold text-gray-800 text-sm leading-tight mb-1 text-wrap">{entry.title}</p>
                            {#if entry.author}
                                <p class="text-xs text-gray-500 uppercase tracking-wide mb-2">{entry.author}</p>
                            {/if}

                            <!-- Categories -->
                            {#if entry.categories && entry.categories.length > 0}
                                <div class="flex flex-wrap gap-1 justify-center">
                                    {#each entry.categories as cat}
                                        <span class="px-2 py-0.5 bg-blue-50 text-blue-600 text-[10px] uppercase font-bold rounded-full border border-blue-100">
                                            {cat}
                                        </span>
                                    {/each}
                                </div>
                            {/if}
                        </div>
                    {/if}
                </button>

                <!-- Controls (Compact) -->
                <div class="bg-gray-50 p-2 border-t border-gray-200 space-y-2 shrink-0">
                    
                    <!-- Classification -->
                    <div class="grid grid-cols-3 gap-2">
                        {#each getClassOptions() as t}
                            <button 
                                class="py-2 px-1 text-xs font-bold rounded-lg uppercase border-2 transition-all
                                {timeClass === t 
                                    ? 'border-blue-600 bg-blue-600 text-white shadow-inner scale-95' 
                                    : 'border-gray-200 bg-white text-gray-400 hover:border-gray-300'}"
                                on:click={() => setTimeClass(t)}
                            >
                                {t}
                            </button>
                        {/each}
                    </div>

                    <!-- Star Rating -->
                    <div class="flex justify-between items-center bg-white p-2 rounded-lg border border-gray-200 shadow-sm">
                        <span class="text-[10px] font-bold text-gray-400 uppercase">Rating:</span>
                        <div class="flex space-x-2">
                            {#each [1, 2, 3, 4, 5] as star}
                                <button 
                                    on:click={() => setRating(star)}
                                    class="text-2xl focus:outline-none transition-transform active:scale-125"
                                >
                                    <span class={star <= rating ? 'text-yellow-400' : 'text-gray-200'}>★</span>
                                </button>
                            {/each}
                        </div>
                    </div>

                    <!-- Action Row -->
                    <div class="flex gap-2">
                        <button 
                            on:click={() => submitVote(true)}
                            class="flex-1 py-3 rounded-lg font-bold text-red-500 border-2 border-red-100 hover:bg-red-50 transition-all uppercase text-xs"
                        >
                            Deny
                        </button>
                        
                        <button 
                            on:click={() => submitVote(false)}
                            disabled={!hasVotedRating || !timeClass}
                            class="flex-[2] py-3 rounded-lg font-bold text-white transition-all shadow-lg text-xs uppercase
                            {!hasVotedRating || !timeClass 
                                ? 'bg-gray-300 cursor-not-allowed shadow-none' 
                                : 'bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 transform active:scale-95'}"
                        >
                            Vote & Next
                        </button>
                    </div>
                </div>
            </div>
        {/if}
    </div>
</div>
