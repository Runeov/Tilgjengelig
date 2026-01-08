import React, { useState } from 'react';
import { AlertCircle, CheckCircle, XCircle, Upload, TrendingUp, Code, BookOpen } from 'lucide-react';

const WCAGAnalyzer = () => {
  const [reports, setReports] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);

  const parseHTMLReport = (htmlContent) => {
    const parser = new DOMParser();
    const doc = parser.parseFromString(htmlContent, 'text/html');
    
    const issues = [];
    const pages = doc.querySelectorAll('.page');
    
    pages.forEach(page => {
      const pageUrl = page.querySelector('.page-url')?.textContent || 'Unknown';
      const issueElements = page.querySelectorAll('.issue');
      
      issueElements.forEach(issue => {
        const ruleId = issue.querySelector('.rule-id')?.textContent || '';
        const criterion = issue.querySelector('.criterion')?.textContent || '';
        const impact = issue.querySelector('.impact')?.textContent || '';
        const description = issue.querySelector('p')?.textContent || '';
        const element = issue.querySelector('.element')?.textContent || '';
        const fix = issue.querySelector('.fix')?.textContent || '';
        
        issues.push({
          page: pageUrl,
          ruleId: ruleId.trim(),
          criterion: criterion.trim(),
          impact: impact.trim().toLowerCase(),
          description: description.trim(),
          element: element.trim(),
          fix: fix.trim()
        });
      });
    });
    
    return issues;
  };

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files);
    setLoading(true);
    
    try {
      const parsedReports = await Promise.all(
        files.map(async (file) => {
          const content = await file.text();
          const issues = parseHTMLReport(content);
          return {
            filename: file.name,
            issues
          };
        })
      );
      
      setReports(parsedReports);
      analyzeIssues(parsedReports);
    } catch (error) {
      console.error('Error parsing reports:', error);
    } finally {
      setLoading(false);
    }
  };

  const analyzeIssues = (reportsData) => {
    const allIssues = reportsData.flatMap(r => r.issues);
    
    // Count by type
    const byRule = {};
    const byImpact = { critical: 0, serious: 0, moderate: 0, minor: 0 };
    const byCriterion = {};
    
    allIssues.forEach(issue => {
      byRule[issue.ruleId] = (byRule[issue.ruleId] || 0) + 1;
      byImpact[issue.impact] = (byImpact[issue.impact] || 0) + 1;
      byCriterion[issue.criterion] = (byCriterion[issue.criterion] || 0) + 1;
    });
    
    // Sort by frequency
    const topIssues = Object.entries(byRule)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([rule, count]) => {
        const example = allIssues.find(i => i.ruleId === rule);
        return {
          rule,
          count,
          impact: example?.impact || 'unknown',
          description: example?.description || '',
          fix: example?.fix || ''
        };
      });
    
    setAnalysis({
      totalIssues: allIssues.length,
      byImpact,
      topIssues,
      reportsCount: reportsData.length
    });
  };

  const getSolutions = (ruleId) => {
    const solutions = {
      'Testregel 2.4.4': {
        title: 'Empty Links (Link Purpose)',
        problem: 'Links without accessible names cannot be understood by screen reader users.',
        solutions: [
          {
            title: 'Add aria-label to social media icons',
            code: `<!-- Before -->
<a class="env-link" href="https://www.facebook.com/...">
  <svg aria-hidden="true">...</svg>
</a>

<!-- After -->
<a class="env-link" 
   href="https://www.facebook.com/..." 
   aria-label="Følg oss på Facebook">
  <svg aria-hidden="true">...</svg>
</a>`,
            priority: 'CRITICAL'
          },
          {
            title: 'Add text to logo links',
            code: `<!-- Before -->
<a class="env-link" href="/">
  <img src="logo.png" alt="">
</a>

<!-- After -->
<a class="env-link" href="/">
  <img src="logo.png" alt="Hasvik Kommune - Hjem">
</a>`,
            priority: 'CRITICAL'
          }
        ]
      },
      'Testregel 1.1.1': {
        title: 'SVG Missing Accessible Names',
        problem: 'SVG icons without accessible names are invisible to screen readers.',
        solutions: [
          {
            title: 'Add title element to decorative SVGs',
            code: `<!-- For decorative icons (most common) -->
<svg aria-hidden="true" role="presentation" class="env-icon">
  <use xlink:href="/sitevision/envision-icons.svg#icon-search"></use>
</svg>

<!-- For meaningful icons -->
<svg aria-labelledby="search-title" role="img" class="env-icon">
  <title id="search-title">Søk</title>
  <use xlink:href="/sitevision/envision-icons.svg#icon-search"></use>
</svg>`,
            priority: 'SERIOUS'
          },
          {
            title: 'Alternative: Use aria-label on parent',
            code: `<!-- Instead of fixing each SVG -->
<button aria-label="Søk">
  <svg aria-hidden="true" class="env-icon">
    <use xlink:href="#icon-search"></use>
  </svg>
</button>`,
            priority: 'SERIOUS'
          }
        ]
      },
      'Testregel 4.1.2': {
        title: 'Region Without Name',
        problem: 'Elements with role="region" need accessible names for navigation.',
        solutions: [
          {
            title: 'Add aria-label to region',
            code: `<!-- Before -->
<div class="sv-custom-module" role="region">
  ...
</div>

<!-- After -->
<div class="sv-custom-module" 
     role="region" 
     aria-label="Hurtiglenker">
  ...
</div>`,
            priority: 'SERIOUS'
          }
        ]
      },
      'Testregel 4.1.1': {
        title: 'Invalid HTML Nesting',
        problem: 'Nested paragraph tags are invalid HTML.',
        solutions: [
          {
            title: 'Remove nested <p> tags',
            code: `<!-- Before -->
<p class="normal">
  Some text
  <p class="normal">Nested paragraph</p>
</p>

<!-- After -->
<div class="normal">
  <p>Some text</p>
  <p>Nested paragraph</p>
</div>`,
            priority: 'MODERATE'
          }
        ]
      }
    };
    
    return solutions[ruleId] || {
      title: ruleId,
      problem: 'See report for details',
      solutions: []
    };
  };

  const getImpactColor = (impact) => {
    const colors = {
      critical: 'bg-red-100 text-red-800 border-red-300',
      serious: 'bg-orange-100 text-orange-800 border-orange-300',
      moderate: 'bg-yellow-100 text-yellow-800 border-yellow-300',
      minor: 'bg-green-100 text-green-800 border-green-300'
    };
    return colors[impact] || 'bg-gray-100 text-gray-800 border-gray-300';
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">
            WCAG Report Analyzer
          </h1>
          <p className="text-gray-600">
            Upload your WCAG accessibility reports to get prioritized solutions
          </p>
        </div>

        {/* Upload Section */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-blue-400 hover:bg-blue-50 transition-colors">
            <div className="flex flex-col items-center justify-center pt-5 pb-6">
              <Upload className="w-10 h-10 mb-3 text-gray-400" />
              <p className="mb-2 text-sm text-gray-500">
                <span className="font-semibold">Click to upload</span> or drag and drop
              </p>
              <p className="text-xs text-gray-500">HTML WCAG reports (multiple files supported)</p>
            </div>
            <input
              type="file"
              className="hidden"
              multiple
              accept=".html"
              onChange={handleFileUpload}
            />
          </label>
        </div>

        {loading && (
          <div className="bg-white rounded-lg shadow-sm p-8 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Analyzing reports...</p>
          </div>
        )}

        {analysis && !loading && (
          <>
            {/* Summary Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-white rounded-lg shadow-sm p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Total Issues</p>
                    <p className="text-2xl font-bold text-gray-900">{analysis.totalIssues}</p>
                  </div>
                  <AlertCircle className="w-8 h-8 text-gray-400" />
                </div>
              </div>
              
              <div className="bg-white rounded-lg shadow-sm p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Critical</p>
                    <p className="text-2xl font-bold text-red-600">{analysis.byImpact.critical}</p>
                  </div>
                  <XCircle className="w-8 h-8 text-red-400" />
                </div>
              </div>
              
              <div className="bg-white rounded-lg shadow-sm p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Serious</p>
                    <p className="text-2xl font-bold text-orange-600">{analysis.byImpact.serious}</p>
                  </div>
                  <AlertCircle className="w-8 h-8 text-orange-400" />
                </div>
              </div>
              
              <div className="bg-white rounded-lg shadow-sm p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Reports</p>
                    <p className="text-2xl font-bold text-gray-900">{analysis.reportsCount}</p>
                  </div>
                  <TrendingUp className="w-8 h-8 text-gray-400" />
                </div>
              </div>
            </div>

            {/* Top Issues with Solutions */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
                <BookOpen className="w-6 h-6" />
                Prioritized Solutions
              </h2>
              
              <div className="space-y-6">
                {analysis.topIssues.map((issue, idx) => {
                  const solution = getSolutions(issue.rule);
                  
                  return (
                    <div key={idx} className="border-l-4 border-blue-500 pl-4">
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-semibold text-gray-900">
                              #{idx + 1} {solution.title}
                            </span>
                            <span className={`px-2 py-1 text-xs font-medium rounded border ${getImpactColor(issue.impact)}`}>
                              {issue.impact.toUpperCase()}
                            </span>
                          </div>
                          <p className="text-sm text-gray-600 mb-2">{issue.description}</p>
                          <p className="text-xs text-gray-500 mb-3">
                            Found <span className="font-semibold text-red-600">{issue.count} times</span> across reports
                          </p>
                        </div>
                      </div>
                      
                      <div className="bg-gray-50 rounded-lg p-4 mb-3">
                        <p className="text-sm font-medium text-gray-700 mb-2">
                          ⚠️ Problem: {solution.problem}
                        </p>
                      </div>
                      
                      {solution.solutions.length > 0 && (
                        <div className="space-y-4">
                          {solution.solutions.map((sol, sidx) => (
                            <div key={sidx} className="bg-blue-50 rounded-lg p-4">
                              <div className="flex items-center gap-2 mb-2">
                                <Code className="w-4 h-4 text-blue-600" />
                                <span className="text-sm font-medium text-blue-900">
                                  Solution {sidx + 1}: {sol.title}
                                </span>
                                <span className={`ml-auto px-2 py-1 text-xs font-medium rounded ${
                                  sol.priority === 'CRITICAL' ? 'bg-red-100 text-red-700' :
                                  sol.priority === 'SERIOUS' ? 'bg-orange-100 text-orange-700' :
                                  'bg-yellow-100 text-yellow-700'
                                }`}>
                                  {sol.priority}
                                </span>
                              </div>
                              <pre className="bg-gray-900 text-gray-100 p-3 rounded text-xs overflow-x-auto">
                                <code>{sol.code}</code>
                              </pre>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Quick Action Summary */}
            <div className="bg-gradient-to-r from-blue-600 to-blue-700 rounded-lg shadow-sm p-6 mt-6 text-white">
              <h3 className="text-lg font-bold mb-3">🎯 Quick Action Plan</h3>
              <div className="space-y-2 text-sm">
                <p>1. Fix all {analysis.byImpact.critical} <strong>CRITICAL</strong> empty links by adding aria-labels</p>
                <p>2. Add role="presentation" to {analysis.byImpact.serious} <strong>SERIOUS</strong> decorative SVGs</p>
                <p>3. Add aria-labels to regions with role="region"</p>
                <p>4. Review and fix HTML nesting issues in content areas</p>
              </div>
              <div className="mt-4 pt-4 border-t border-blue-500">
                <p className="text-xs opacity-90">
                  💡 Tip: Focus on Critical and Serious issues first - they have the biggest impact on users with disabilities.
                </p>
              </div>
            </div>
          </>
        )}

        {!analysis && !loading && (
          <div className="bg-white rounded-lg shadow-sm p-12 text-center">
            <Upload className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">Upload your WCAG reports to get started</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default WCAGAnalyzer;