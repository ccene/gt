import { Component } from '@angular/core';

@Component({
  selector: 'app-root',
  template: `
    <div class="container-fluid">
      <nav class="navbar navbar-expand-lg navbar-dark bg-dark mb-4">
        <div class="container">
          <a class="navbar-brand" routerLink="/">Order Management</a>
          <div class="navbar-nav">
            <a class="nav-link" routerLink="/orders" routerLinkActive="active">Orders</a>
            <a class="nav-link" routerLink="/orders/new" routerLinkActive="active">New Order</a>
          </div>
        </div>
      </nav>
      <div class="container">
        <router-outlet></router-outlet>
      </div>
    </div>
  `,
  styles: [
    `.navbar { margin-bottom: 20px; }`,
    `.container { padding: 20px; }`
  ]
})
export class AppComponent { }
