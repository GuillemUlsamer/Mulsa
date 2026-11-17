import { Routes } from '@angular/router';
import { Runner } from './runner/runner';
import { Playlists } from './playlists/playlists';
import { Settings } from './settings/settings';
import { Setup } from './setup/setup';

export const routes: Routes = [
    { path: 'run/:name', component: Runner },
    { path: 'playlists', component: Playlists },
    { path: 'setup', component: Setup },
    { path: 'setup/:name', component: Setup },
    { path: 'settings', component: Settings },
    { path: '', redirectTo: '/playlists', pathMatch: 'full' },
];